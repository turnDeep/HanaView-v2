const CACHE_NAME = 'hanaview-cache-v1';
const APP_SHELL_URLS = [
  '/',
  '/index.html',
  '/style.css',
  '/app.js',
  '/manifest.json',
  'https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js'
];
const DATA_URL = '/api/data';

// Install event: cache the app shell
self.addEventListener('install', event => {
  console.log('Service Worker: Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('Service Worker: Caching app shell');
      return cache.addAll(APP_SHELL_URLS);
    })
  );
});

// Activate event: clean up old caches
self.addEventListener('activate', event => {
  console.log('Service Worker: Activating...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cache => {
          if (cache !== CACHE_NAME) {
            console.log('Service Worker: Clearing old cache', cache);
            return caches.delete(cache);
          }
        })
      );
    })
  );
});

// Fetch event: serve from cache or network
self.addEventListener('fetch', event => {
  const { request } = event;

  // For API data, use a "stale-while-revalidate" strategy
  if (request.url.includes(DATA_URL)) {
    event.respondWith(
      caches.open(CACHE_NAME).then(cache => {
        return cache.match(request).then(cachedResponse => {
          const fetchPromise = fetch(request).then(networkResponse => {
            cache.put(request, networkResponse.clone());
            return networkResponse;
          });
          // Return cached response immediately, then update cache in the background.
          return cachedResponse || fetchPromise;
        });
      })
    );
    return;
  }

  // For other requests (app shell), use a "cache-first" strategy
  event.respondWith(
    caches.match(request).then(response => {
      return response || fetch(request);
    })
  );
});
