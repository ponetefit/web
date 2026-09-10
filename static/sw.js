// sw.js — Service Worker mínimo de PONETE FIT
//
// ¿Por qué existe este archivo?
// Chrome/Android (y el resto de los navegadores basados en Chromium)
// SOLO consideran "instalable" a una PWA si detectan un Service Worker
// activo con al menos un listener de 'fetch'. Sin esto, el navegador
// nunca dispara el evento "beforeinstallprompt" y el botón "Instalar App"
// del HTML se queda sin hacer nada al tocarlo, aunque el manifest esté
// perfecto.
//
// Este Service Worker cachea el HTML principal para que la app también
// abra (aunque sea en una versión desactualizada) sin conexión.

const CACHE_NAME = 'ponete-fit-v1';

self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            // Cachea la página actual (el propio HTML) al instalar.
            return cache.add(self.registration.scope);
        }).catch(() => {
            // Si falla el cacheo inicial (por ejemplo, sin red), no rompemos
            // la instalación del Service Worker.
        })
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((nombres) => {
            return Promise.all(
                nombres
                    .filter((nombre) => nombre !== CACHE_NAME)
                    .map((nombre) => caches.delete(nombre))
            );
        }).then(() => self.clients.claim())
    );
});

// Estrategia: red primero, y si falla (sin conexión), cae al cache.
self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    event.respondWith(
        fetch(event.request)
            .then((respuesta) => {
                const copia = respuesta.clone();
                caches.open(CACHE_NAME).then((cache) => {
                    cache.put(event.request, copia);
                });
                return respuesta;
            })
            .catch(() => {
                return caches.match(event.request).then((respuestaCache) => {
                    return respuestaCache || caches.match(self.registration.scope);
                });
            })
    );
});
