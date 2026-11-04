// Import the functions you need from the SDKs you need
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.0/firebase-app.js";
import { getDatabase, ref, push, set, onValue } from "https://www.gstatic.com/firebasejs/11.0.0/firebase-database.js";

// Your web app's Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyB0Z63JJUBUkhLBMR0YAWJWvevUsJG6ifo",
    authDomain: "afrikan-54834.firebaseapp.com",
    databaseURL: "https://afrikan-54834-default-rtdb.asia-southeast1.firebasedatabase.app",
    projectId: "afrikan-54834",
    storageBucket: "afrikan-54834.firebasestorage.app",
    messagingSenderId: "397857302474",
    appId: "1:397857302474:web:b4081751694621d98dd133",
    measurementId: "G-0HRJ99RD12"
};

// Initialize Firebase & Database
const app = initializeApp(firebaseConfig);
const db = getDatabase(app);

// Función para guardar un artículo en Realtime Database
export function guardarArticuloFirebase(articulo) {
    const articulosRef = ref(db, 'articulos');
    const nuevoArticuloRef = push(articulosRef);
    return set(nuevoArticuloRef, {
        ...articulo,
        createdAt: Date.now()
    });
}

// Función para escuchar los artículos en tiempo real
export function obtenerArticulosFirebase(callback) {
    const articulosRef = ref(db, 'articulos');
    onValue(articulosRef, (snapshot) => {
        const data = snapshot.val();
        const articulos = [];
        if (data) {
            for (let id in data) {
                articulos.push({ id, ...data[id] });
            }
        }
        callback(articulos);
    });
}
