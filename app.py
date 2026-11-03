from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def inicio():
    productos = [
        {
            "nombre": "Camiseta",
            "precio": 20,
            "descripcion": "Camiseta de algodón"
        },
        {
            "nombre": "Gorra",
            "precio": 15,
            "descripcion": "Gorra deportiva"
        }
    ]

    return render_template(
        'index.html',
        productos=productos
    )

if __name__ == '__main__':
    app.run(debug=True)