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

# URL de tu Firebase Realtime Database
FIREBASE_DB_URL = "https://african-movies-8568b-default-rtdb.firebaseio.com"

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

GOOGLE_CLIENT_ID = "1062928384474-edan147q560ubs30p9fa2ins3vsj8v1q.apps.googleusercontent.com"

# --- FUNCIONES DE COMUNICACIÓN CON FIREBASE REST API ---

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
    articles = load_articles()
    for art in articles:
        if art.get('slug') == slug:
            return art
    return None

def get_article_by_id(art_id):
    articles = load_articles()
    for art in articles:
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
        profile_file = request.files.get('profile_pic')

        user['country'] = country
        user['city'] = city
        user['phone'] = phone

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

        # COMPRESIÓN DE FOTO A BASE64 PARA PERSISTENCIA EN FIREBASE
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
