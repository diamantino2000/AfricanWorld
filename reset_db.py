import os

db_path = 'africanworld.db'
instance_db_path = 'instance/africanworld.db'

# Borrar base de datos principal si existe
if os.path.exists(db_path):
    os.remove(db_path)
    print("Base de datos principal 'africanworld.db' eliminada con éxito.")

# Borrar base de datos en instance si existe
if os.path.exists(instance_db_path):
    os.remove(instance_db_path)
    print("Base de datos de 'instance/' eliminada con éxito.")

print("¡Listo! Ya puedes iniciar `python app.py` y registrarte desde cero con cualquier correo y usuario.")