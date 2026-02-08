/**
 * Argon Social Network - Service Worker
 * Minimal service worker for PWA installation
 */

const CACHE_NAME = 'argon-v1';

// Install event - just claim immediately
self.addEventListener('install', (event) => {
  console.log('[SW] Service Worker installing');
  self.skipWaiting();
});

// Activate event - take control of all pages
self.addEventListener('activate', (event) => {
  console.log('[SW] Service Worker activated');
  event.waitUntil(self.clients.claim());
});

// Fetch event - network-first strategy (no offline caching yet)
self.addEventListener('fetch', (event) => {
  event.respondWith(
    fetch(event.request).catch(() => {
      // Could add offline fallback here later
      return new Response('Offline - please check your connection', {
        status: 503,
        statusText: 'Service Unavailable'
      });
    })
  );
}); 
