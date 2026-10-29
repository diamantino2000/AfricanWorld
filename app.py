from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from google.oauth2 import id_token
from google.auth.transport import requests
import os
import json
import unicodedata
import re
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
from sqlalchemy import text

# Configurar rutas absolutas basadas en la ubicación de app.py
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'african-world-secret-key-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'africanworld_v2.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

GOOGLE_CLIENT_ID = "1062928384474-edan147q560ubs30p9fa2ins3vsj8v1q.apps.googleusercontent.com"
USERS_JSON_FILE = os.path.join(basedir, 'cuentas.json')
DENUNCIAS_JSON_FILE = os.path.join(basedir, 'denuncias.json')

def load_json_users():
    if not os.path.exists(USERS_JSON_FILE):
        return []
    try:
        with open(USERS_JSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def save_json_users(users_list):
    try:
        with open(USERS_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_list, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando usuarios: {e}")

def load_denuncias():
    if not os.path.exists(DENUNCIAS_JSON_FILE):
        return []
    try:
        with open(DENUNCIAS_JSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def save_denuncias(denuncias_list):
    try:
        with open(DENUNCIAS_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(denuncias_list, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando denuncias: {e}")

def add_notification(target_username, message, link="#"):
    users = load_json_users()
    for u in users:
        if u['username'] == target_username:
            if 'notifications' not in u:
                u['notifications'] = []
            u['notifications'].insert(0, {
                "id": len(u['notifications']) + 1,
                "message": message,
                "link": link,
                "read": False,
                "date": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
            })
            break
    save_json_users(users)

db = SQLAlchemy(app)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    country = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    description = db.Column(db.Text, nullable=False)
    username = db.Column(db.String(80), nullable=False)
    images = db.Column(db.Text, nullable=True)
    views = db.Column(db.Integer, default=0)
    is_sold = db.Column(db.Boolean, default=False)
    comments = db.relationship('Comment', backref='article', cascade="all, delete-orphan", lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    date = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()
    try:
        db.session.execute(text("ALTER TABLE article ADD COLUMN is_sold BOOLEAN DEFAULT 0"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        db.session.execute(text("ALTER TABLE article ADD COLUMN price FLOAT DEFAULT 0.0"))
        db.session.commit()
    except Exception:
        db.session.rollback()

def slugify(text_value):
    text_value = unicodedata.normalize('NFKD', text_value).encode('ascii', 'ignore').decode('utf-8')
    text_value = re.sub(r'[^\w\s-]', '', text_value).strip().lower()
    return re.sub(r'[-\s]+', '-', text_value)

@app.route('/')
def index():
    if 'username' not in session:
        return render_template('intro.html', google_client_id=GOOGLE_CLIENT_ID)
    
    search = request.args.get('search', '')
    if search:
        articles = Article.query.filter(
            (Article.title.contains(search)) | 
            (Article.country.contains(search)) | 
            (Article.city.contains(search))
        ).order_by(Article.id.desc()).all()
    else:
        articles = Article.query.order_by(Article.id.desc()).all()
    
    users = load_json_users()
    current_user = next((u for u in users if u['username'] == session.get('username')), None)

    return render_template('index.html', articles=articles, search=search, current_user=current_user, google_client_id=GOOGLE_CLIENT_ID)

@app.route('/buscar-usuarios')
def search_users():
    query = request.args.get('q', '').strip().lower()
    users = load_json_users()
    matched_users = []

    if query:
        for u in users:
            if query in u['username'].lower() or query in u.get('email', '').lower():
                matched_users.append(u)

    current_user = next((u for u in users if u['username'] == session.get('username')), None) if 'username' in session else None

    return render_template('Busca_user.html', query=query, users=matched_users, current_user=current_user)

@app.route('/terminos')
def terms():
    return render_template('terminos.html')

@app.route('/mark-notifications-read', methods=['POST'])
def mark_notifications_read():
    if 'username' in session:
        users = load_json_users()
        for u in users:
            if u['username'] == session['username']:
                for n in u.get('notifications', []):
                    n['read'] = True
                break
        save_json_users(users)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 401

@app.route('/report-article/<int:article_id>', methods=['POST'])
def report_article(article_id):
    if 'username' not in session:
        flash('Debes iniciar sesión para realizar una denuncia.', 'error')
        return redirect(url_for('index'))

    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Por favor describe el motivo de la denuncia.', 'error')
        return redirect(request.referrer or url_for('index'))

    article = Article.query.get_or_404(article_id)

    denuncias = load_denuncias()
    denuncias.append({
        "id": len(denuncias) + 1,
        "article_id": article.id,
        "article_title": article.title,
        "article_slug": article.slug,
        "article_owner": article.username,
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
        id_info = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        email = id_info['email']
        name = id_info.get('name', email.split('@')[0])
        picture = id_info.get('picture', '/static/uploads/default_user.png')

        users = load_json_users()
        user = next((u for u in users if u['email'] == email), None)

        if not user:
            base_username = slugify(name.replace(" ", "_"))
            username = base_username if base_username else "usuario"
            counter = 1
            while any(u['username'] == username for u in users):
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
        return jsonify({"status": "success", "redirect": url_for('index')})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/articulo/<slug>')
def view_article(slug):
    article = Article.query.filter_by(slug=slug).first_or_404()
    
    if 'visited_articles' not in session:
        session['visited_articles'] = []

    if article.id not in session['visited_articles']:
        article.views += 1
        db.session.commit()
        session['visited_articles'].append(article.id)
        session.modified = True
    
    users = load_json_users()
    current_user = next((u for u in users if u['username'] == session.get('username')), None) if 'username' in session else None
    author = next((u for u in users if u['username'] == article.username), None)
    
    avg_rating = 0
    if article.comments:
        avg_rating = round(sum(c.rating for c in article.comments) / len(article.comments), 1)

    return render_template('article_detail.html', article=article, current_user=current_user, author=author, avg_rating=avg_rating)

@app.route('/articulo/<slug>/comment', methods=['POST'])
def add_comment(slug):
    if 'username' not in session:
        flash('Debes iniciar sesión para comentar.', 'error')
        return redirect(url_for('view_article', slug=slug))

    article = Article.query.filter_by(slug=slug).first_or_404()
    content = request.form.get('content')
    rating = int(request.form.get('rating', 5))

    new_comment = Comment(article_id=article.id, username=session['username'], content=content, rating=rating)
    db.session.add(new_comment)
    db.session.commit()

    if article.username != session['username']:
        add_notification(
            article.username,
            f"💬 @{session['username']} comentó en tu publicación '{article.title}'",
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
    current_u = next((u for u in users if u['username'] == session['username']), None)
    target_u = next((u for u in users if u['username'] == username), None)

    if current_u and target_u:
        if 'following' not in current_u: current_u['following'] = []
        if 'followers' not in target_u: target_u['followers'] = []

        if username in current_u['following']:
            current_u['following'].remove(username)
            target_u['followers'].remove(session['username'])
            is_following = False
        else:
            current_u['following'].append(username)
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

    article = Article.query.get_or_404(article_id)
    if article.username == session['username']:
        article.is_sold = not article.is_sold
        db.session.commit()
        flash('Estado del artículo actualizado.', 'success')

    return redirect(url_for('view_article', slug=article.slug))

@app.route('/articulo/<int:article_id>/delete', methods=['POST'])
def delete_article(article_id):
    if 'username' not in session:
        return redirect(url_for('index'))

    article = Article.query.get_or_404(article_id)
    if article.username == session['username']:
        db.session.delete(article)
        db.session.commit()
        flash('La publicación ha sido eliminada con éxito.', 'success')
        return redirect(url_for('profile', username=session['username']))

    return redirect(url_for('index'))

@app.route('/carrito/add/<int:article_id>', methods=['POST'])
def add_to_cart(article_id):
    if 'username' not in session:
        flash('Inicia sesión para usar el carrito.', 'error')
        return redirect(url_for('index'))
    
    if 'cart' not in session:
        session['cart'] = []
    
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
    users = load_json_users()
    current_user = next((u for u in users if u['username'] == session.get('username')), None) if 'username' in session else None
    
    cart_ids = session.get('cart', [])
    cart_articles = Article.query.filter(Article.id.in_(cart_ids)).all() if cart_ids else []
    
    return render_template('carrito.html', articles=cart_articles, current_user=current_user)

@app.route('/perfil/<username>')
def profile(username):
    users = load_json_users()
    profile_user = next((u for u in users if u['username'] == username), None)
    if not profile_user:
        return redirect(url_for('index'))
    
    current_user = next((u for u in users if u['username'] == session.get('username')), None) if 'username' in session else None
    user_articles = Article.query.filter_by(username=username).order_by(Article.id.desc()).all()

    return render_template('cuenta.html', profile_user=profile_user, current_user=current_user, articles=user_articles)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'username' not in session:
        return redirect(url_for('index'))

    users = load_json_users()
    user = next((u for u in users if u['username'] == session['username']), None)
    if not user:
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        profile_file = request.files.get('profile_pic')

        if new_username and new_username != user['username']:
            if any(u['username'] == new_username for u in users):
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

            articles_to_update = Article.query.filter_by(username=old_username).all()
            for art in articles_to_update:
                art.username = new_username
            db.session.commit()

        if profile_file and profile_file.filename != '':
            filename = secure_filename(profile_file.filename)
            filepath_rel = f"static/uploads/profile_{user['id']}_{filename}"
            filepath_abs = os.path.join(basedir, filepath_rel)
            profile_file.save(filepath_abs)
            user['profile_pic'] = f"/{filepath_rel}"

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
    for file in uploaded_files[:17]:
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath_rel = f"static/uploads/{filename}"
            filepath_abs = os.path.join(basedir, filepath_rel)
            file.save(filepath_abs)
            image_paths.append(f"/{filepath_rel}")

    base_slug = slugify(title)
    slug = base_slug
    counter = 1
    while Article.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    new_article = Article(
        title=title, 
        price=price, 
        slug=slug, 
        country=country, 
        city=city, 
        email=email, 
        phone=phone, 
        description=description, 
        username=session['username'], 
        images=",".join(image_paths)
    )
    db.session.add(new_article)
    db.session.commit()
    return redirect(url_for('view_article', slug=new_article.slug))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
