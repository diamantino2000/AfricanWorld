import sqlite3

# Conectar a la base de datos SQLite
conn = sqlite3.connect('africanworld.db')
cursor = conn.cursor()

# Añadir la columna 'slug' si no existe
try:
    cursor.execute("ALTER TABLE article ADD COLUMN slug VARCHAR(200);")
    print("Columna 'slug' añadida con éxito.")
except sqlite3.OperationalError:
    print("La columna 'slug' ya existe.")

# Añadir la columna 'phone' si no existe
try:
    cursor.execute("ALTER TABLE article ADD COLUMN phone VARCHAR(30);")
    print("Columna 'phone' añadida con éxito.")
except sqlite3.OperationalError:
    print("La columna 'phone' ya existe.")

# Añadir la columna 'profile_pic' a user si no existe
try:
    cursor.execute("ALTER TABLE user ADD COLUMN profile_pic VARCHAR(200) DEFAULT '/static/uploads/default_user.png';")
    print("Columna 'profile_pic' añadida con éxito.")
except sqlite3.OperationalError:
    print("La columna 'profile_pic' ya existe.")

# Añadir la columna 'last_username_change' a user si no existe
try:
    cursor.execute("ALTER TABLE user ADD COLUMN last_username_change DATETIME;")
    print("Columna 'last_username_change' añadida con éxito.")
except sqlite3.OperationalError:
    print("La columna 'last_username_change' ya existe.")

conn.commit()
conn.close()
print("¡Base de datos corregida correctamente!")