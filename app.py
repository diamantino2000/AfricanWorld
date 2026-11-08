from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
import requests
import unicodedata
import re
import base64
from datetime import datetime, timezone

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'african-world-secret-key-2026')

FIREBASE_DB_URL = "https://african-movies-8568b-default-rtdb.firebaseio.com"

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

GOOGLE_CLIENT_ID = "1062928384474-edan147q560ubs30p9fa2ins3vsj8v1q.apps.googleusercontent.com"
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY', '3ca96164517ba9751a3ef0e3032206ef')

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
def index():
    if 'username' not in session:
        return render_template('intro.html', google_client_id=GOOGLE_CLIENT_ID)

    search = request.args.get('search', '').lower()
    articles = load_articles()
    
    if search:
        filtered = []
        for art in articles:
            if search in art.get('title', '').lower() or search in art.get('country', '').lower() or search in art.get('city', '').lower():
                filtered.append(art)
        articles = filtered
    
    users = load_json_users()
    current_user = next((u for u in users if u.get('username') == session.get('username')), None)

    return render_template('index.html', articles=articles, search=search, current_user=current_user, google_client_id=GOOGLE_CLIENT_ID)

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

@app.route('/articulo/<slug>')
def article_detail(slug):
    articles = load_articles()
    article = next((art for art in articles if art.get('slug') == slug), None)
    if not article:
        flash("El artículo no existe.", "error")
        return redirect(url_for('index'))
    
    article['views'] = article.get('views', 0) + 1
    fb_put(f"articles/{article['firebase_id']}", article)

    users = load_json_users()
    author = next((u for u in users if u.get('username') == article.get('username')), None)
    
    comments = article.get('comments', [])
    avg_rating = sum(c.get('rating', 0) for c in comments) / len(comments) if comments else 0

    return render_template('article_detail.html', article=article, author=author, avg_rating=round(avg_rating, 1))

@app.route('/articulo/<path:article_id>/delete', methods=['POST'])
def delete_article(article_id):
    if 'username' not in session:
        return redirect(url_for('index'))
    
    articles = load_articles()
    # CORREGIDO AQUÍ (Uso correcto de paréntesis)
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

    article_data = {
        "numeric_id": int(datetime.now().timestamp()),
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
    slug = f"{slug_base}-{article_data['numeric_id']}"
    article_data['slug'] = slug

    fb_put(f"articles/{slug}", article_data)
    flash('¡Artículo publicado con éxito!', 'success')
    return redirect(url_for('profile', username=session['username']))

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
        # 1. Eliminar todas las publicaciones creadas por el usuario en Firebase
        articles = load_articles()
        for art in articles:
            if art.get('username') == current_username:
                fb_delete(f"articles/{art.get('firebase_id')}")

        # 2. Eliminar al usuario de Firebase
        safe_key = current_username.replace(".", "_").replace("#", "_").replace("$", "_").replace("[", "_").replace("]", "_")
        fb_delete(f"users/{safe_key}")

        # 3. Limpiar sesión actual
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
    
    # Filtrar los artículos que están en el carrito del usuario
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
        session.modified = True
        flash('Artículo eliminado del carrito.', 'success')
        
    return redirect(url_for('view_cart'))
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
        comments = article.get('comments', [])
        new_comment = {
            "username": session['username'],
            "content": content,
            "rating": rating_val,
            "date": datetime.now(timezone.utc).isoformat()
        }
        comments.append(new_comment)
        article['comments'] = comments

        # Guardar en Firebase
        fb_put(f"articles/{article['firebase_id']}", article)
        flash('¡Comentario publicado con éxito!', 'success')
    else:
        flash('El artículo no existe.', 'error')

    return redirect(url_for('article_detail', slug=slug))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
