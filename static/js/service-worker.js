/* ==========================================================================
   Gemini Insights - Progressive Web App (PWA) Service Worker
   Conservative Cache Strategy: Zero-Private-Data Caching Guarantee
   ========================================================================== */

const CACHE_NAME = 'gemini-insights-static-v10';

// Static, public assets safe for offline caching (NO private or role data)
const PRECACHE_ASSETS = [
  '/offline/',
  '/manifest.webmanifest',
  '/static/css/theme.css',
  '/static/js/theme.js',
  '/static/img/logo.png',
  '/static/pwa/icons/icon-192x192.png',
  '/static/pwa/icons/icon-512x512.png',
  '/static/pwa/icons/apple-touch-icon.png',
  '/static/pwa/icons/favicon-32x32.png',
  '/static/pwa/icons/badge-96x96.png',
  '/static/pwa/icons/badge-72x72.png',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js'
];

// Patterns that must NEVER be cached or read from cache
const SENSITIVE_URL_PATTERNS = [
  '/admin/',
  '/login/',
  '/logout/',
  '/api/',
  '/reports/',
  '/compliance/',
  '/audit/',
  '/dashboard/',
  '/accounts/',
  '/profile/',
  '/password/'
];

// Helper to check if a URL contains sensitive / role-specific paths
function isSensitiveUrl(url) {
  try {
    const urlObj = new URL(url);
    const pathname = urlObj.pathname.toLowerCase();
    return SENSITIVE_URL_PATTERNS.some(pattern => pathname.includes(pattern));
  } catch (e) {
    return false;
  }
}

/* --------------------------------------------------------------------------
   1. Install Event: Pre-cache static assets
   -------------------------------------------------------------------------- */
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // Use individual promises with catch so single failed optional asset won't block install
      return Promise.allSettled(
        PRECACHE_ASSETS.map((assetUrl) => {
          return cache.add(new Request(assetUrl, { cache: 'reload' })).catch((err) => {
            console.warn('[SW] Could not pre-cache asset:', assetUrl, err);
          });
        })
      );
    }).then(() => self.skipWaiting())
  );
});

/* --------------------------------------------------------------------------
   2. Activate Event: Clean up outdated caches and claim clients
   -------------------------------------------------------------------------- */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => {
            console.log('[SW] Purging outdated cache:', name);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

/* --------------------------------------------------------------------------
   3. Fetch Event: Strict privacy-preserving fetch handling
   -------------------------------------------------------------------------- */
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = request.url;

  // RULE 1: Non-GET requests (POST, PUT, PATCH, DELETE) ALWAYS go directly to network
  if (request.method !== 'GET') {
    return;
  }

  // RULE 2: Navigation requests (HTML page loads)
  // Network-First with safe /offline/ fallback.
  // NEVER cache HTML responses to prevent storing authenticated report/dashboard data.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => {
        return caches.match('/offline/').then((offlineResponse) => {
          if (offlineResponse) {
            return offlineResponse;
          }
          return new Response(
            '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Offline - Gemini Insights</title></head><body><h1>Offline</h1><p>You are offline. Reconnect to view or submit reports.</p></body></html>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        });
      })
    );
    return;
  }

  // RULE 3: Sensitive endpoints (reports, compliance, auth, admin) -> Always bypass cache
  if (isSensitiveUrl(url)) {
    return;
  }

  // RULE 4: Static assets (CSS, JS, Fonts, Images under /static/ or trusted CDNs)
  // Cache-First strategy with network fallback
  const isStaticAsset = url.includes('/static/') || 
                        url.includes('cdn.jsdelivr.net') || 
                        url.includes('fonts.googleapis.com') || 
                        url.includes('fonts.gstatic.com') ||
                        url.endsWith('.png') ||
                        url.endsWith('.jpg') ||
                        url.endsWith('.jpeg') ||
                        url.endsWith('.svg') ||
                        url.endsWith('.ico') ||
                        url.endsWith('.css') ||
                        url.endsWith('.js');

  if (isStaticAsset) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }

        return fetch(request).then((networkResponse) => {
          // Verify valid response before caching
          if (
            networkResponse && 
            networkResponse.status === 200 && 
            networkResponse.type !== 'opaque'
          ) {
            const cacheControl = networkResponse.headers.get('Cache-Control');
            if (!cacheControl || !cacheControl.includes('no-store')) {
              const responseToCache = networkResponse.clone();
              caches.open(CACHE_NAME).then((cache) => {
                cache.put(request, responseToCache);
              });
            }
          }
          return networkResponse;
        }).catch((err) => {
          // If network fails for an asset, let it fail gracefully
          console.warn('[SW] Static asset fetch failed:', url);
        });
      })
    );
  }
});

/* --------------------------------------------------------------------------
   4. Push Event: Handle incoming push messages from server (browser closed / background)
   -------------------------------------------------------------------------- */
self.addEventListener('push', (event) => {
  let data = {
    title: 'Gemini Insights',
    body: 'You have a new update in Gemini Insights.',
    icon: '/static/pwa/icons/icon-192x192.png',
    badge: '/static/pwa/icons/badge-96x96.png',
    tag: 'gemini-notification',
    url: '/tasks/'
  };

  if (event.data) {
    try {
      const payload = event.data.json();
      data = Object.assign({}, data, payload);
    } catch (e) {
      data.body = event.data.text() || data.body;
    }
  }

  const options = {
    body: data.body,
    icon: data.icon || '/static/pwa/icons/icon-192x192.png',
    badge: data.badge || '/static/pwa/icons/badge-96x96.png',
    tag: data.tag || 'gemini-notification',
    renotify: true,
    requireInteraction: false,
    silent: false,
    data: { url: data.url || '/tasks/' }
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

/* --------------------------------------------------------------------------
   5. Notification Click: Open or focus the relevant page
   -------------------------------------------------------------------------- */
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const rawUrl = (event.notification.data && event.notification.data.url) || '/tasks/';
  const targetUrl = new URL(rawUrl, self.location.origin).href;

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // 1. If an open window is already at this exact target URL, focus it
      for (const client of clientList) {
        if (client.url === targetUrl && 'focus' in client) {
          return client.focus();
        }
      }
      // 2. If an open window belongs to this origin, focus and navigate it
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.focus();
          if (client.navigate) return client.navigate(targetUrl);
          return;
        }
      }
      // 3. Otherwise open new window
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

/* --------------------------------------------------------------------------
   6. Message Event: Handle messages from the page (e.g. show notification)
   -------------------------------------------------------------------------- */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
    const { title, body, icon, badge, tag, url } = event.data;
    self.registration.showNotification(title || 'Gemini Insights', {
      body: body || 'You have a new notification.',
      icon: icon || '/static/pwa/icons/icon-192x192.png',
      badge: badge || '/static/pwa/icons/badge-96x96.png',
      tag: tag || 'gemini-notification',
      renotify: true,
      requireInteraction: false,
      data: { url: url || '/tasks/' }
    });
  }
});
