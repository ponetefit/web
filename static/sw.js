// sw.js — Service Worker de PONETE FIT
// Este archivo tiene que estar subido al servidor, en la MISMA carpeta
// donde vive alumno.html (por ejemplo: web/static/sw.js si alumno.html
// está en web/static/alumno.html).

var CACHE_NAME = 'ponetefit-v1';

self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            return cache.addAll([
                self.registration.scope
            ]).catch(function() {
                // Si falla (ej: sin conexión durante la instalación), no rompe nada
            });
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', function(event) {
    event.waitUntil(
        caches.keys().then(function(cacheNames) {
            return Promise.all(
                cacheNames.filter(function(name) {
                    return name !== CACHE_NAME;
                }).map(function(name) {
                    return caches.delete(name);
                })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', function(event) {
    // Solo maneja peticiones GET
    if (event.request.method !== 'GET') return;

    event.respondWith(
        // Primero red, si falla usa el cache
        fetch(event.request).then(function(response) {
            if (response && response.status === 200) {
                var responseClone = response.clone();
                caches.open(CACHE_NAME).then(function(cache) {
                    cache.put(event.request, responseClone);
                });
            }
            return response;
        }).catch(function() {
            return caches.match(event.request).then(function(response) {
                return response || new Response('Offline — no hay cache disponible', {
                    status: 503,
                    headers: { 'Content-Type': 'text/plain' }
                });
            });
        })
    );
});
