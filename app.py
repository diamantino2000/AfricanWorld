from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
import requests
import unicodedata
import re
import base64
from datetime import datetime, timezone
from werkzeug.utils import secure_filename

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'african-world-secret-key-2026')

# URL de tu Firebase Realtime Database
FIREBASE_DB_URL = "https://african-movies-8568b-default-rtdb.firebaseio.com"

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

GOOGLE_CLIENT_ID = "1062928384474-edan147q560ubs30p9fa2ins3vsj8v1q.apps.googleusercontent.com"

# ==========================================
# FUNCIONES DE COMUNICACIÓN CON FIREBASE REST API
# ==========================================

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

def fb_post(path, data):
    try:
        response = requests.post(f"{FIREBASE_DB_URL}/{path}.json", json=data)
        if response.status_code == 200:
            return response.json().get('name')
    except Exception as e:
        print(f"Error agregando en Firebase ({path}): {e}")
    return None

def fb_delete(path):
    try:
        response = requests.delete(f"{FIREBASE_DB_URL}/{path}.json")
        return response.status_code == 200
    except Exception as e:
        print(f"Error borrando en Firebase ({path}): {e}")
    return False

# ==========================================
# ADAPTADORES DE DATOS
# ==========================================

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

def load_denuncias():
    data = fb_get("denuncias")
    if not data:
        return []
    denuncias_list = []
    for d_id, d_data in data.items():
        if isinstance(d_data, dict):
            d_data['firebase_id'] = d_id
            denuncias_list.append(d_data)
    return denuncias_list

def save_denuncias(denuncias_list):
    if denuncias_list:
        last_d = denuncias_list[-1]
        fb_post("denuncias", last_d)

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

def get_article_by_slug(slug):
    for art in load_articles():
        if art.get('slug') == slug:
            return art
    return None

def get_article_by_id(art_id):
    for art in load_articles():
        if art.get('id') == int(art_id) or art.get('firebase_id') == str(art_id):
            return art
    return None

def add_notification(target_username, message, link="#"):
    users = load_json_users()
    for u in users:
        if u.get('username') == target_username:
            if 'notifications' not in u:
                u['notifications'] = []
            u['notifications'].insert(0, {
                "id": len(u['notifications']) + 1,
                "message": message,
                "link": link,
                "read": False,
                "date": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
            })
            save_json_users(users)
            break

def slugify(text_value):
    text_value = unicodedata.normalize('NFKD', text_value).encode('ascii', 'ignore').decode('utf-8')
    text_value = re.sub(r'[^\w\s-]', '', text_value).strip().lower()
    return re.sub(r'[-\s]+', '-', text_value)

# ==========================================
# RUTAS DE LA APLICACIÓN
# ==========================================

@app.route('/')
def index():
    if 'username' not in session:
        return render_template('intro.html', google_client_id=GOOGLE_CLIENT_ID)

    search = request.args.get('search', '').lower()
    articles = load_articles()
    
    if search:
        articles = [
            art for art in articles 
            if search in art.get('title', '').lower() 
            or search in art.get('country', '').lower() 
            or search in art.get('city', '').lower()
        ]
    
    users = load_json_users()
    current_user = next((u for u in users if u.get('username') == session.get('username')), None)

    return render_template('index.html', articles=articles, search=search, current_user=current_user, google_client_id=GOOGLE_CLIENT_ID)

@app.route('/buscar-usuarios')
def search_users():
    if 'username' not in session:
        return redirect(url_for('index'))

    query = request.args.get('q', '').strip().lower()
    users = load_json_users()
    matched_users = []

    if query:
        matched_users = [
            u for u in users 
            if query in u.get('username', '').lower() 
            or query in u.get('email', '').lower()
        ]

    current_user = next((u for u in users if u.get('username') == session.get('username')), None)
    return render_template('Busca_user.html', query=query, users=matched_users, current_user=current_user)

@app.route('/terminos')
def terms():
    return render_template('terminos.html')

@app.route('/mark-notifications-read', methods=['POST'])
def mark_notifications_read():
    if 'username' in session:
        users = load_json_users()
        for u in users:
            if u.get('username') == session['username']:
                for n in u.get('notifications', []):
                    n['read'] = True
                save_json_users(users)
                break
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 401

@app.route('/get-notifications-json')
def get_notifications_json():
    if 'username' not in session:
        return jsonify({"status": "error", "unread_count": 0, "notifications": []}), 401
    
    users = load_json_users()
    current_user = next((u for u in users if u.get('username') == session['username']), None)
    notifications = current_user.get('notifications', []) if current_user else []
    
    unread_count = sum(1 for n in notifications if not n.get('read', False))
    
    formatted_notifications = [{
        "message": noti.get("message"),
        "link": noti.get("link"),
        "read": noti.get("read", False),
        "time_ago": noti.get("date", "")
    } for noti in notifications]

    return jsonify({
        "status": "success",
        "unread_count": unread_count,
        "notifications": formatted_notifications
    })

@app.route('/report-article/<int:article_id>', methods=['POST'])
def report_article(article_id):
    if 'username' not in session:
        flash('Debes iniciar sesión para realizar una denuncia.', 'error')
        return redirect(url_for('index'))

    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Por favor describe el motivo de la denuncia.', 'error')
        return redirect(request.referrer or url_for('index'))

    article = get_article_by_id(article_id)
    if not article:
        flash('Artículo no encontrado.', 'error')
        return redirect(url_for('index'))

    denuncias = load_denuncias()
    denuncias.append({
        "id": len(denuncias) + 1,
        "article_id": article.get('id'),
        "article_title": article.get('title'),
        "article_slug": article.get('slug'),
        "article_owner": article.get('username'),
        "reported_by": session['username'],
        "reason": reason,
        "date": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
    })
    save_denuncias(denuncias)

    flash('La denuncia ha sido enviada con éxito.', 'success')
    return redirect(request.referrer or url_for('index'))

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
                "followers": [],
                "following": [],
                "notifications": []
            }
            users.append(user)
            save_json_users(users)

        session['username'] = user['username']
        session['email'] = user['email']
        session['profile_pic'] = user.get('profile_pic', picture)
        return jsonify({"status": "success", "redirect": url_for('index')})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/articulo/<slug>')
def view_article(slug):
    if 'username' not in session:
        return redirect(url_for('index'))

    article = get_article_by_slug(slug)
    if not article:
        return "Artículo no encontrado", 404
    
    if 'visited_articles' not in session:
        session['visited_articles'] = []

    if article.get('id') not in session['visited_articles']:
        article['views'] = article.get('views', 0) + 1
        fb_put(f"articles/{article.get('firebase_id')}", article)
        session['visited_articles'].append(article.get('id'))
        session.modified = True
    
    users = load_json_users()
    current_user = next((u for u in users if u.get('username') == session.get('username')), None)
    author = next((u for u in users if u.get('username') == article.get('username')), None)
    
    comments = article.get('comments', [])
    avg_rating = round(sum(c.get('rating', 5) for c in comments) / len(comments), 1) if comments else 0

    return render_template('article_detail.html', article=article, current_user=current_user, author=author, avg_rating=avg_rating, comments=comments)

@app.route('/articulo/<slug>/comment', methods=['POST'])
def add_comment(slug):
    if 'username' not in session:
        flash('Debes iniciar sesión para comentar.', 'error')
        return redirect(url_for('view_article', slug=slug))

    article = get_article_by_slug(slug)
    if not article:
        return "Artículo no encontrado", 404

    content = request.form.get('content')
    rating = int(request.form.get('rating', 5))

    if 'comments' not in article:
        article['comments'] = []

    article['comments'].append({
        "username": session['username'],
        "content": content,
        "rating": rating,
        "date": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
    })
    
    fb_put(f"articles/{article.get('firebase_id')}", article)

    if article.get('username') != session['username']:
        add_notification(
            article.get('username'),
            f"💬 @{session['username']} comentó en tu publicación '{article.get('title')}'",
            url_for('view_article', slug=slug)
        )

    flash('¡Comentario publicado!', 'success')
    return redirect(url_for('view_article', slug=slug))

@app.route('/follow/<username>', methods=['POST'])
def follow_user(username):
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Inicia sesión primero"}), 401

    if session['username'] == username:
        return jsonify({"status": "error", "message": "No puedes seguirte a ti mismo"}), 400

    users = load_json_users()
    current_u = next((u for u in users if u.get('username') == session['username']), None)
    target_u = next((u for u in users if u.get('username') == username), None)

    if current_u and target_u:
        current_u.setdefault('following', [])
        target_u.setdefault('followers', [])

        if username in current_u['following']:
            current_u['following'].remove(username)
            if session['username'] in target_u['followers']:
                target_u['followers'].remove(session['username'])
            is_following = False
        else:
            current_u['following'].append(username)
            if session['username'] not in target_u['followers']:
                target_u['followers'].append(session['username'])
            is_following = True

            add_notification(
                username,
                f"👤 @{session['username']} ha comenzado a seguirte",
                url_for('profile', username=session['username'])
            )

        save_json_users(users)
        return jsonify({"status": "success", "is_following": is_following, "followers_count": len(target_u['followers'])})

    return jsonify({"status": "error", "message": "Usuario no encontrado"}), 404

@app.route('/articulo/<int:article_id>/mark-sold', methods=['POST'])
def mark_sold(article_id):
    if 'username' not in session:
        return redirect(url_for('index'))

    article = get_article_by_id(article_id)
    if article and article.get('username') == session['username']:
        article['is_sold'] = not article.get('is_sold', False)
        fb_put(f"articles/{article.get('firebase_id')}", article)
        flash('Estado del artículo actualizado.', 'success')
        return redirect(url_for('view_article', slug=article.get('slug')))

    return redirect(url_for('index'))

@app.route('/articulo/<int:article_id>/delete', methods=['POST'])
def delete_article(article_id):
    if 'username' not in session:
        return redirect(url_for('index'))

    article = get_article_by_id(article_id)
    if article and article.get('username') == session['username']:
        fb_delete(f"articles/{article.get('firebase_id')}")
        flash('La publicación ha sido eliminada con éxito.', 'success')
        return redirect(url_for('profile', username=session['username']))

    return redirect(url_for('index'))

@app.route('/carrito/add/<int:article_id>', methods=['POST'])
def add_to_cart(article_id):
    if 'username' not in session:
        flash('Inicia sesión para usar el carrito.', 'error')
        return redirect(url_for('index'))
    
    session.setdefault('cart', [])
    
    if article_id not in session['cart']:
        session['cart'].append(article_id)
        session.modified = True
        flash('¡Artículo añadido al carrito!', 'success')
    else:
        flash('Este artículo ya está en tu carrito.', 'info')
        
    return redirect(request.referrer or url_for('index'))

@app.route('/carrito/remove/<int:article_id>', methods=['POST'])
def remove_from_cart(article_id):
    if 'cart' in session and article_id in session['cart']:
        session['cart'].remove(article_id)
        session.modified = True
        flash('Artículo eliminado del carrito.', 'success')
    return redirect(url_for('view_cart'))

@app.route('/carrito')
def view_cart():
    if 'username' not in session:
        return redirect(url_for('index'))

    users = load_json_users()
    current_user = next((u for u in users if u.get('username') == session.get('username')), None)
    
    cart_ids = session.get('cart', [])
    cart_articles = [art for art in load_articles() if art.get('id') in cart_ids]
    
    return render_template('carrito.html', articles=cart_articles, current_user=current_user)

@app.route('/perfil/<username>')
def profile(username):
    if 'username' not in session:
        return redirect(url_for('index'))

    users = load_json_users()
    profile_user = next((u for u in users if u.get('username') == username), None)
    
    if not profile_user:
        if session.get('username') == username:
            profile_user = {
                "id": len(users) + 1,
                "username": username,
                "email": session.get('email', ''),
                "profile_pic": session.get('profile_pic', '/static/uploads/default_user.png'),
                "followers": [],
                "following": [],
                "notifications": []
            }
            users.append(profile_user)
            save_json_users(users)
        else:
            flash("El usuario no existe.", "error")
            return redirect(url_for('index'))
    
    current_user = next((u for u in users if u.get('username') == session.get('username')), None)
    user_articles = [art for art in load_articles() if art.get('username') == username]

    return render_template('cuenta.html', profile_user=profile_user, current_user=current_user, articles=user_articles)

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
        profile_file = request.files.get('profile_pic')

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

            for art in load_articles():
                if art.get('username') == old_username:
                    art['username'] = new_username
                    fb_put(f"articles/{art.get('firebase_id')}", art)

        if profile_file and profile_file.filename != '':
            try:
                file_bytes = profile_file.read()
                encoded_image = base64.b64encode(file_bytes).decode('utf-8')
                mimetype = profile_file.mimetype or 'image/jpeg'
                base64_url = f"data:{mimetype};base64,{encoded_image}"
                
                user['profile_pic'] = base64_url
                session['profile_pic'] = base64_url
            except Exception as e:
                print(f"Error procesando la foto para Firebase: {e}")
                flash('No se pudo procesar la imagen de perfil.', 'error')

        save_json_users(users)
        flash('¡Ajustes actualizados con éxito!', 'success')
        return redirect(url_for('profile', username=user['username']))

    return render_template('settings.html', user=user)

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('index'))

@app.route('/publish', methods=['POST'])
def publish():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    title = request.form.get('title')
    price = request.form.get('price')
    country = request.form.get('country')
    city = request.form.get('city')
    email = request.form.get('email')
    phone = request.form.get('phone')
    description = request.form.get('description')
    uploaded_files = request.files.getlist('photos')

    try:
        price = float(price)
    except (ValueError, TypeError):
        price = 0.0

    image_paths = []
    imgbb_api_key = os.environ.get('IMGBB_API_KEY', '3ca96164517ba9751a3ef0e3032206ef')

    for file in uploaded_files[:17]:
        if file and file.filename != '':
            try:
                response = requests.post(
                    "https://api.imgbb.com/1/upload",
                    data={"key": imgbb_api_key},
                    files={"image": file.read()}
                )
                result = response.json()
                if result.get("success"):
                    image_paths.append(result["data"]["url"])
            except Exception as e:
                print(f"Error subiendo a ImgBB: {e}")

    base_slug = slugify(title)
    slug = base_slug
    counter = 1
    existing_slugs = [a.get('slug') for a in load_articles()]
    while slug in existing_slugs:
        slug = f"{base_slug}-{counter}"
        counter += 1

    new_article = {
        "numeric_id": int(datetime.now(timezone.utc).timestamp()),
        "title": title, 
        "price": price, 
        "slug": slug, 
        "country": country, 
        "city": city, 
        "email": email, 
        "phone": phone, 
        "description": description, 
        "username": session['username'], 
        "images": ",".join(image_paths),
        "views": 0,
        "is_sold": False,
        "comments": []
    }
    
    fb_post("articles", new_article)
    return redirect(url_for('view_article', slug=slug))

@app.route('/publicar')
def publicar_page():
    if 'username' not in session:
        flash('Debes iniciar sesión para publicar.', 'error')
        return redirect(url_for('index'))
    return redirect(url_for('profile', username=session['username'], publish='1'))

@app.route('/eliminar-cuenta')
def eliminar_cuenta():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    username = session['username']
    
    for u in load_json_users():
        if u.get('username') == username and 'firebase_id' in u:
            fb_delete(f"users/{u.get('firebase_id')}")
            break
            
    for art in load_articles():
        if art.get('username') == username and 'firebase_id' in art:
            fb_delete(f"articles/{art.get('firebase_id')}")
    
    session.clear()
    flash('Tu cuenta ha sido eliminada permanentemente.', 'success')
    return redirect(url_for('index'))

@app.route('/complete-onboarding', methods=['POST'])
def complete_onboarding():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "No hay sesión activa"}), 401

    data = request.get_json() or {}
    country = data.get('country', '').strip()
    city = data.get('city', '').strip()
    phone = data.get('phone', '').strip()

    if not country or not city or not phone:
        return jsonify({"status": "error", "message": "Todos los campos son obligatorios"}), 400

    users = load_json_users()
    user = next((u for u in users if u.get('username') == session['username']), None)
    
    if user:
        user['country'] = country
        user['city'] = city
        user['phone'] = phone
        save_json_users(users)
        return jsonify({"status": "success", "redirect": url_for('index')})

    return jsonify({"status": "error", "message": "Usuario no encontrado"}), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
