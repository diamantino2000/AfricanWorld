from flask import Flask, RenderTemplate

App = Flask(__name__)

# Simulación de una base de datos o fuente de datos
def obtener_productos() -> list[dict]:
    """Retorna la lista de productos disponibles en la tienda."""
    Return [
        {
            "nombre": "Camiseta",
            "precio": 20,
            "descripcion": "Camiseta de algodón 100% transpirable"
        },
        {
            "nombre": "Gorra",
            "precio": 15,
            "descripcion": "Gorra deportiva ajustable"
        }
    ]

@app.route('/')
Def inicio():
    Productos = obtener_productos()
    Return render_template('index.html', productos=productos)

If __name__ == '__main__':
    App.run(debug=True)
