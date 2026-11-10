from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
import requests
import unicodedata
import re
import base64
from datetime import datetime, timezone, timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, template_folder='.')

# --- CLAVE SECRETA ESTÁTICA Y PERMANENTE (NO USA OS.ENVIRON) ---
app.config['SECRET_KEY'] = 'african-world-static-permanent-secret-key-2026-fixed'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

FIREBASE_DB_URL = "https://african-movies-8568b-default-rtdb.firebaseio.com"

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

GOOGLE_CLIENT_ID = "1062928384474-edan147q560ubs30p9fa2ins3vsj8v1q.apps.googleusercontent.com"
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY', '3ca96164517ba9751a3ef0e3032206ef')

# --- CONTEXT PROCESSOR GLOBAL PARA MANTENER EL IDIOMA EN CADA TEMPLATE ---
@app.context_processor
def inject_user_language():
    current_lang = session.get('language', 'es')
    return dict(current_lang=current_lang)

# --- FUNCIONES DE IMGBB Y FIREBASE ---

def upload_to_imgbb(file_bytes):
    if not IMGBB_API_KEY:
        encoded = base64.b64encode(file_bytes).decode('utf-8')
        return f"data:image/jpeg;base64,{encoded}"
    try:
        url = "https://api.imgbb.com/1/upload"
        payload = {
            "key": IMGBB_API_KEY,
            "image": base64.b64encode(file_bytes).decode('utf-8')
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get('success'):
                return res_data['data']['url']
    except Exception as e:
        print(f"Error subiendo a ImgBB: {e}")
    
    encoded = base64.b64encode(file_bytes).decode('utf-8')
    return f"data:image/jpeg;base64,{encoded}"

def fb_get(path):
    try:
        response = requests.get(f"{FIREBASE_DB_URL}/{path}.json")
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error leyendo de Firebase ({path}): {e}")
    return None

def fb_put(path, data):
    try:
        response = requests.put(f"{FIREBASE_DB_URL}/{path}.json", json=data)
        return response.status_code == 200
    except Exception as e:
        print(f"Error escribiendo en Firebase ({path}): {e}")
    return False

def fb_delete(path):
    try:
        response = requests.delete(f"{FIREBASE_DB_URL}/{path}.json")
        return response.status_code == 200
    except Exception as e:
        print(f"Error borrando en Firebase ({path}): {e}")
    return False

# --- ADAPTADORES DE DATOS ---

def load_json_users():
    data = fb_get("users")
    if not data:
        return []
    users_list = []
    for u_id, u_data in data.items():
        if isinstance(u_data, dict):
            u_data['firebase_id'] = u_id
            users_list.append(u_data)
    return users_list

def save_json_users(users_list):
    for u_data in users_list:
        username = u_data.get('username')
        if username:
            safe_key = username.replace(".", "_").replace("#", "_").replace("$", "_").replace("[", "_").replace("]", "_")
            fb_put(f"users/{safe_key}", u_data)

def load_articles():
    data = fb_get("articles")
    if not data:
        return []
    articles_list = []
    for a_id, a_data in data.items():
        if isinstance(a_data, dict):
            a_data['id'] = a_data.get('numeric_id', hash(a_id) % 100000)
            a_data['firebase_id'] = a_id
            articles_list.append(a_data)
    articles_list.sort(key=lambda x: x.get('id', 0), reverse=True)
    return articles_list

def slugify(text_value):
    text_value = unicodedata.normalize('NFKD', text_value).encode('ascii', 'ignore').decode('utf-8')
    text_value = re.sub(r'[^\w\s-]', '', text_value).strip().lower()
    return re.sub(r'[-\s]+', '-', text_value)

# --- RUTAS DE LA APLICACIÓN ---

@app.route('/')
@app.route('/page-<int:page>')
def index(page=1):
    if 'username' not in session:
        return render_template('intro.html', google_client_id=GOOGLE_CLIENT_ID)

    users = load_json_users()
    current_user = next((u for u in users if u.get('username') == session.get('username')), None)

    # Actualizar idioma en la sesión si existe en el usuario
    if current_user and current_user.get('language'):
        session['language'] = current_user.get('language')

    needs_onboarding = False
    if current_user and (not current_user.get('country') or not current_user.get('city') or not current_user.get('phone')):
        needs_onboarding = True

    search = request.args.get('search', '').lower()
    articles = load_articles()
    
    if search:
        filtered = []
        for art in articles:
            if search in art.get('title', '').lower() or search in art.get('country', '').lower() or search in art.get('city', '').lower():
                filtered.append(art)
        articles = filtered
    
    per_page = 20
    total_articles = len(articles)
    total_pages = (total_articles + per_page - 1) // per_page
    
    if total_pages < 1:
        total_pages = 1
        
    if page < 1:
        return redirect(url_for('index'))
    if page > total_pages and total_pages > 0:
        return redirect(url_for('index', page=total_pages) if total_pages > 1 else url_for('index'))

    start = (page - 1) * per_page
    end = start + per_page
    paginated_articles = articles[start:end]

    return render_template(
        'index.html', 
        articles=paginated_articles, 
        search=search, 
        current_user=current_user, 
        google_client_id=GOOGLE_CLIENT_ID,
        current_page=page,
        total_pages=total_pages,
        needs_onboarding=needs_onboarding
    )

@app.route('/terminos')
def terminos():
    return render_template('terminos.html')

@app.route('/buscar-usuarios')
def buscar_usuarios():
    query = request.args.get('q', '').lower()
    users = load_json_users()
    filtered_users = []
    if query:
        for u in users:
            if query in u.get('username', '').lower() or query in u.get('email', '').lower():
                filtered_users.append(u)
    else:
        filtered_users = users
    return render_template('Busca_user.html', users=filtered_users, query=query)

# --- RUTAS DE ACCIONES EN ARTÍCULOS ---

@app.route('/report-article/<article_id>', methods=['POST'])
@app.route('/articulo/<slug>/report', methods=['POST'])
def report_article(article_id=None, slug=None):
    if 'username' not in session:
        return redirect(url_for('index'))

    reason = request.form.get('reason', '').strip()
    articles = load_articles()
    
    article = None
    if slug:
        article = next((art for art in articles if art.get('slug') == slug), None)
    elif article_id:
        article = next((art for art in articles if str(art.get('id')) == str(article_id) or art.get('firebase_id') == article_id), None)

    if not article:
        flash('El artículo no existe.', 'error')
        return redirect(url_for('index'))

    if not reason:
        flash('El motivo de la denuncia no puede estar vacío.', 'error')
        return redirect(url_for('article_detail', slug=article.get('slug')) if article.get('slug') else url_for('index'))

    report_data = {
        "article_id": article.get('firebase_id'),
        "article_slug": article.get('slug', ''),
        "article_title": article.get('title', ''),
        "seller_username": article.get('username', ''),
        "reporter_username": session['username'],
        "reason": reason,
        "date": datetime.now(timezone.utc).isoformat()
    }

    report_key = f"rep_{int(datetime.now().timestamp())}"
    success = fb_put(f"reports/{report_key}", report_data)

    if success:
        flash('Tu denuncia ha sido enviada y registrada correctamente.', 'success')
    else:
        flash('Hubo un error al enviar la denuncia. Inténtalo de nuevo.', 'error')

    if slug or article.get('slug'):
        return redirect(url_for('article_detail', slug=article.get('slug')))
    return redirect(url_for('index'))

@app.route('/articulo/<slug>/comment', methods=['POST'])
def add_comment(slug):
    if 'username' not in session:
        return redirect(url_for('index'))

    content = request.form.get('content', '').strip()
    rating = request.form.get('rating', '5')

    try:
        rating_val = int(rating)
    except ValueError:
        rating_val = 5

    if not content:
        flash('El comentario no puede estar vacío.', 'error')
        return redirect(url_for('article_detail', slug=slug))

    articles = load_articles()
    article = next((art for art in articles if art.get('slug') == slug), None)

    if article:
        commenter_username = session['username']
        seller_username = article.get('username')

        # 1. Crear y agregar el nuevo comentario al artículo
        comments = article.get('comments', [])
        new_comment = {
            "username": commenter_username,
            "content": content,
            "rating": rating_val,
            "date": datetime.now(timezone.utc).isoformat()
        }
        comments.append(new_comment)
        article['comments'] = comments

        # Guardar el artículo actualizado en Firebase
        fb_put(f"articles/{article['firebase_id']}", article)

        # 2. CREAR NOTIFICACIÓN PARA EL VENDEDOR (solo si no es el mismo que comenta)
        if seller_username and seller_username != commenter_username:
            users = load_json_users()
            seller_user = next((u for u in users if u.get('username') == seller_username), None)

            if seller_user:
                if 'notifications' not in seller_user:
                    seller_user['notifications'] = []

                # Insertar la notificación al principio de la lista
                seller_user['notifications'].insert(0, {
                    "message": f"@{commenter_username} ha comentado en tu artículo '{article.get('title')}'",
                    "link": f"/articulo/{slug}",
                    "read": False,
                    "date": datetime.now(timezone.utc).isoformat()
                })

                # Guardar los datos del usuario vendedor en Firebase
                save_json_users(users)

        flash('¡Comentario publicado con éxito!', 'success')
    else:
        flash('El artículo no existe.', 'error')

    return redirect(url_for('article_detail', slug=slug))

@app.route('/articulo/<path:article_id>/delete', methods=['POST'])
def delete_article(article_id):
    if 'username' not in session:
        return redirect(url_for('index'))
    
    articles = load_articles()
    article = next((art for art in articles if str(art.get('id')) == str(article_id) or art.get('firebase_id') == article_id or art.get('slug') == article_id), None)
    
    if article:
        if article.get('username') == session['username']:
            fb_delete(f"articles/{article['firebase_id']}")
            flash('¡Publicación eliminada con éxito!', 'success')
        else:
            flash('No tienes permiso para eliminar esta publicación.', 'error')
    else:
        flash('El artículo no existe.', 'error')
        
    return redirect(url_for('profile', username=session['username']))

@app.route('/articulo/<path:article_id>/mark-sold', methods=['POST'])
def mark_article_sold(article_id):
    if 'username' not in session:
        return redirect(url_for('index'))
    
    articles = load_articles()
    article = next((art for art in articles if str(art.get('id')) == str(article_id) or art.get('firebase_id') == article_id or art.get('slug') == article_id), None)
    
    if article:
        if article.get('username') == session['username']:
            # Alternar el estado de is_sold (True <-> False)
            article['is_sold'] = not article.get('is_sold', False)
            fb_put(f"articles/{article['firebase_id']}", article)
            
            status_text = "marcado como comprado" if article['is_sold'] else "marcado como disponible"
            flash(f'¡Artículo {status_text} con éxito!', 'success')
        else:
            flash('No tienes permiso para modificar este artículo.', 'error')
    else:
        flash('El artículo no existe.', 'error')
        
    # Redirigir de vuelta a la página del detalle del artículo
    return redirect(url_for('article_detail', slug=article.get('slug'))) if article and article.get('slug') else redirect(url_for('index'))

@app.route('/articulo/<slug>')
def article_detail(slug):
    articles = load_articles()
    article = next((art for art in articles if art.get('slug') == slug), None)
    if not article:
        flash("El artículo no existe.", "error")
        return redirect(url_for('index'))
    
    if 'viewed_articles' not in session:
        session['viewed_articles'] = []

    if article['firebase_id'] not in session['viewed_articles']:
        article['views'] = article.get('views', 0) + 1
        fb_put(f"articles/{article['firebase_id']}", article)
        session['viewed_articles'].append(article['firebase_id'])
        session.modified = True

    users = load_json_users()
    author = next((u for u in users if u.get('username') == article.get('username')), None)
    
    comments = article.get('comments', [])
    ratings = [c.get('rating', 0) for c in comments if isinstance(c.get('rating'), (int, float)) and c.get('rating', 0) > 0]
    
    total_reviews = len(ratings)
    avg_rating = sum(ratings) / total_reviews if total_reviews > 0 else 0.0

    return render_template(
        'article_detail.html', 
        article=article, 
        author=author, 
        avg_rating=round(avg_rating, 1),
        total_reviews=total_reviews
    )

# --- RUTAS DE USUARIO Y CONFIGURACIÓN ---

@app.route('/complete-onboarding', methods=['POST'])
def complete_onboarding():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "No hay sesión activa"}), 401

    data = request.get_json() or {}
    country = data.get('country', '').strip()
    city = data.get('city', '').strip()
    phone = data.get('phone', '').strip()
    language = data.get('language', 'es').strip()

    if not country or not city or not phone:
        return jsonify({"status": "error", "message": "Todos los campos son obligatorios"}), 400

    users = load_json_users()
    user = next((u for u in users if u.get('username') == session['username']), None)
    
    if user:
        user['country'] = country
        user['city'] = city
        user['phone'] = phone
        user['language'] = language
        save_json_users(users)
        
        # GUARDAR IDIOMA EN LA SESIÓN DE FLASK
        session['language'] = language
        session.permanent = True
        session.modified = True
        return jsonify({"status": "success", "redirect": url_for('index')})

    return jsonify({"status": "error", "message": "Usuario no encontrado"}), 404

@app.route('/google-login-real', methods=['POST'])
def google_login_real():
    data = request.get_json() or {}
    token = data.get('credential')
    if not token:
        return jsonify({"status": "error", "message": "Token no proporcionado"}), 400
    try:
        id_info = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        email = id_info['email']
        name = id_info.get('name', email.split('@')[0])
        picture = id_info.get('picture', '/static/uploads/default_user.png')

        users = load_json_users()
        user = next((u for u in users if u.get('email') == email), None)

        if not user:
            base_username = slugify(name.replace(" ", "_"))
            username = base_username if base_username else "usuario"
            counter = 1
            while any(u.get('username') == username for u in users):
                username = f"{base_username}{counter}"
                counter += 1

            user = {
                "id": len(users) + 1,
                "username": username,
                "email": email,
                "profile_pic": picture,
                "country": "",
                "city": "",
                "phone": "",
                "language": "es",
                "followers": [],
                "following": [],
                "notifications": []
            }
            users.append(user)
            save_json_users(users)

        session['username'] = user['username']
        session['email'] = user['email']
        session['profile_pic'] = user.get('profile_pic', picture)
        session['language'] = user.get('language', 'es')
        session.permanent = True  # Mantiene la sesión abierta permanentemente
        return jsonify({"status": "success", "redirect": url_for('index')})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'username' not in session:
        return redirect(url_for('index'))

    users = load_json_users()
    user = next((u for u in users if u.get('username') == session['username']), None)
    if not user:
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        country = request.form.get('country', '').strip()
        city = request.form.get('city', '').strip()
        phone = request.form.get('phone', '').strip()
        language = request.form.get('language', 'es').strip()
        profile_file = request.files.get('profile_pic')

        user['country'] = country
        user['city'] = city
        user['phone'] = phone
        user['language'] = language
        session['language'] = language

        if new_username and new_username != user['username']:
            if any(u.get('username') == new_username for u in users):
                flash('Este nombre de usuario ya está en uso.', 'error')
                return redirect(url_for('settings'))

            if user.get('last_username_change'):
                last_change = datetime.fromisoformat(user['last_username_change'])
                days_passed = (datetime.now(timezone.utc) - last_change).days
                if days_passed < 7:
                    days_left = 7 - days_passed
                    flash(f'Debes esperar {days_left} día(s) más para cambiar tu nombre de usuario.', 'error')
                    return redirect(url_for('settings'))

            old_username = user['username']
            user['username'] = new_username
            user['last_username_change'] = datetime.now(timezone.utc).isoformat()
            session['username'] = new_username

            articles = load_articles()
            for art in articles:
                if art.get('username') == old_username:
                    art['username'] = new_username
                    fb_put(f"articles/{art.get('firebase_id')}", art)

        if profile_file and profile_file.filename != '':
            try:
                file_bytes = profile_file.read()
                if len(file_bytes) > 0:
                    img_url = upload_to_imgbb(file_bytes)
                    user['profile_pic'] = img_url
                    session['profile_pic'] = img_url
            except Exception as e:
                print(f"Error procesando la foto de perfil: {e}")
                flash('No se pudo procesar la imagen de perfil.', 'error')

        save_json_users(users)
        session.permanent = True
        flash('¡Ajustes actualizados con éxito!', 'success')
        return redirect(url_for('profile', username=user['username']))

    return render_template('settings.html', user=user)

@app.route('/perfil/<username>')
def profile(username):
    if 'username' not in session:
        return redirect(url_for('index'))

    users = load_json_users()
    profile_user = next((u for u in users if u.get('username') == username), None)
    
    if not profile_user:
        flash("El usuario no existe.", "error")
        return redirect(url_for('index'))
    
    current_user = next((u for u in users if u.get('username') == session.get('username')), None)
    all_articles = load_articles()
    user_articles = [art for art in all_articles if art.get('username') == username]

    return render_template('cuenta.html', profile_user=profile_user, current_user=current_user, articles=user_articles)

@app.route('/follow/<username>', methods=['POST'])
def toggle_follow(username):
    if 'username' not in session:
        return jsonify({"status": "error", "message": "No hay sesión activa"}), 401

    current_username = session['username']
    if current_username == username:
        return jsonify({"status": "error", "message": "No te puedes seguir a ti mismo"}), 400

    users = load_json_users()
    
    # Buscar al usuario actual y al usuario perfilado
    current_user = next((u for u in users if u.get('username') == current_username), None)
    profile_user = next((u for u in users if u.get('username') == username), None)

    if not current_user or not profile_user:
        return jsonify({"status": "error", "message": "Usuario no encontrado"}), 404

    # Inicializar listas si no existen
    if 'following' not in current_user:
        current_user['following'] = []
    if 'followers' not in profile_user:
        profile_user['followers'] = []

    is_following = False

    # Alternar estado de seguir / dejar de seguir
    if username in current_user['following']:
        current_user['following'].remove(username)
        if current_username in profile_user['followers']:
            profile_user['followers'].remove(current_username)
        is_following = False
    else:
        current_user['following'].append(username)
        if current_username not in profile_user['followers']:
            profile_user['followers'].append(current_username)
        is_following = True

        # Crear notificación para el usuario seguido
        if 'notifications' not in profile_user:
            profile_user['notifications'] = []
        
        profile_user['notifications'].insert(0, {
            "message": f"@{current_username} ha empezado a seguirte.",
            "link": f"/perfil/{current_username}",
            "read": False,
            "date": datetime.now(timezone.utc).isoformat()
        })

    # Guardar cambios en Firebase
    save_json_users(users)

    return jsonify({
        "status": "success",
        "is_following": is_following,
        "followers_count": len(profile_user['followers'])
    })

@app.route('/publish', methods=['POST'])
def publish_article():
    if 'username' not in session:
        return redirect(url_for('index'))

    title = request.form.get('title', '').strip()
    price_val = request.form.get('price', '0').strip()
    description = request.form.get('description', '').strip()
    uploaded_files = request.files.getlist('photos')

    users = load_json_users()
    current_user = next((u for u in users if u.get('username') == session['username']), None)

    if not current_user:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('index'))

    country = current_user.get('country', '')
    city = current_user.get('city', '')
    phone = current_user.get('phone', '')

    try:
        price = float(price_val)
    except ValueError:
        price = 0.0

    image_urls = []
    for file in uploaded_files:
        if file and file.filename != '':
            try:
                file_bytes = file.read()
                if len(file_bytes) > 0:
                    img_url = upload_to_imgbb(file_bytes)
                    image_urls.append(img_url)
            except Exception as e:
                print(f"Error subiendo foto de artículo a ImgBB: {e}")

    if not image_urls:
        image_urls.append("/static/uploads/default_item.png")

    current_timestamp = int(datetime.now().timestamp())
    existing_articles = load_articles()
    
    user_articles = [art for art in existing_articles if art.get('username') == session['username']]
    
    if len(user_articles) == 0:
        numeric_id = current_timestamp
    else:
        numeric_id = 0

    article_data = {
        "numeric_id": numeric_id,
        "title": title,
        "price": price,
        "phone": phone,
        "country": country,
        "city": city,
        "description": description,
        "username": session['username'],
        "images": ",".join(image_urls),
        "views": 0,
        "is_sold": False,
        "comments": []
    }

    slug_base = slugify(title)
    slug = f"{slug_base}-{current_timestamp}"
    article_data['slug'] = slug

    fb_put(f"articles/{slug}", article_data)
    flash('¡Artículo publicado con éxito!', 'success')
    return redirect(url_for('profile', username=session['username']))

@app.route('/mark-notifications-read', methods=['POST'])
def mark_notifications_read():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "No hay sesión activa"}), 401

    users = load_json_users()
    user = next((u for u in users if u.get('username') == session['username']), None)

    if user and user.get('notifications'):
        # Marcar todas las notificaciones como leídas
        for noti in user['notifications']:
            noti['read'] = True
        
        save_json_users(users)
        return jsonify({"status": "success"})

    return jsonify({"status": "error", "message": "No hay notificaciones"}), 404


@app.route('/get-notifications-json')
def get_notifications_json():
    if 'username' not in session:
        return jsonify({"status": "error", "unread_count": 0, "notifications": []})

    users = load_json_users()
    user = next((u for u in users if u.get('username') == session['username']), None)

    if not user:
        return jsonify({"status": "error", "unread_count": 0, "notifications": []})

    notifications = user.get('notifications', [])
    unread_count = len([n for n in notifications if not n.get('read', False)])

    return jsonify({
        "status": "success",
        "unread_count": unread_count,
        "notifications": notifications
    })

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('index'))

@app.route('/account/delete', methods=['POST'])
def delete_account():
    if 'username' not in session:
        return redirect(url_for('index'))

    current_username = session['username']
    users = load_json_users()
    user = next((u for u in users if u.get('username') == current_username), None)

    if user:
        articles = load_articles()
        for art in articles:
            if art.get('username') == current_username:
                fb_delete(f"articles/{art.get('firebase_id')}")

        safe_key = current_username.replace(".", "_").replace("#", "_").replace("$", "_").replace("[", "_").replace("]", "_")
        fb_delete(f"users/{safe_key}")

        session.clear()
        flash('Tu cuenta y todas tus publicaciones han sido eliminadas correctamente.', 'info')
        return redirect(url_for('index'))

    flash('Usuario no encontrado.', 'error')
    return redirect(url_for('index'))
    
@app.route('/carrito')
def view_cart():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    cart_ids = session.get('cart', [])
    all_articles = load_articles()
    
    cart_articles = [art for art in all_articles if art.get('id') in cart_ids or str(art.get('id')) in [str(x) for x in cart_ids]]
    
    return render_template('carrito.html', articles=cart_articles)

@app.route('/carrito/add/<int:article_id>', methods=['POST'])
def add_to_cart(article_id):
    if 'username' not in session:
        return redirect(url_for('index'))
    
    if 'cart' not in session:
        session['cart'] = []
    
    if article_id not in session['cart']:
        session['cart'].append(article_id)
        session.permanent = True
        session.modified = True
        flash('¡Artículo añadido al carrito!', 'success')
    else:
        flash('Este artículo ya está en tu carrito.', 'info')
        
    return redirect(url_for('view_cart'))

@app.route('/carrito/remove/<int:article_id>', methods=['POST'])
def remove_from_cart(article_id):
    if 'username' not in session:
        return redirect(url_for('index'))
    
    if 'cart' in session:
        session['cart'] = [item for item in session['cart'] if item != article_id]
        session.permanent = True
        session.modified = True
        flash('Artículo eliminado del carrito.', 'success')
        
    return redirect(url_for('view_cart'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
