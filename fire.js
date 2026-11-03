// Importa las funciones necesarias de los SDKs de Firebase
import { initializeApp } from "https://www.gstatic.com/firebasejs/13.2.0/firebase-app.js";
import { getDatabase, ref, set, push, onValue } from "https://www.gstatic.com/firebasejs/13.2.0/firebase-database.js";

// Tu configuración web de Firebase
const firebaseConfig = {
  apiKey: "AIzaSyB0Z63JJUBUkhLBMR0YAWJWvevUsJG6ifo",
  authDomain: "afrikan-54834.firebaseapp.com",
  databaseURL: "https://afrikan-54834-default-rtdb.asia-southeast1.firebasedatabase.app",
  projectId: "afrikan-54834",
  storageBucket: "afrikan-54834.appspot.com",
  messagingSenderId: "397857302474",
  appId: "1:397857302474:web:b4081751694621d98dd133",
  measurementId: "G-0HRJ99RD12"
};

// Inicializar Firebase y la Base de Datos
const app = initializeApp(firebaseConfig);
const db = getDatabase(app);

// Función para guardar publicaciones en tiempo real
export function guardarArticulo(titulo, precio, ciudad, descripcion) {
    const nuevoArticuloRef = push(ref(db, 'articles'));
    return set(nuevoArticuloRef, {
        title: titulo,
        price: precio,
        city: ciudad,
        description: description,
        fecha: new Date().toISOString()
    });
}

// Función para escuchar las publicaciones en tiempo real
export function obtenerArticulos(callback) {
    const articlesRef = ref(db, 'articles');
    onValue(articlesRef, (snapshot) => {
        const data = snapshot.val();
        const lista = data ? Object.values(data) : [];
        callback(lista);
    });
}
