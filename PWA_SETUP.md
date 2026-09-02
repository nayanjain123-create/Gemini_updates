# Progressive Web App (PWA) Setup & Installation Guide

Gemini Insights is now a Progressive Web App (PWA). This enables employees and bosses to install the application directly onto their mobile and desktop home screens, launch it in a full-screen, app-like standalone window, and safely handle offline conditions without exposing sensitive compliance records.

---

## 🚀 Key Features & Architectural Guarantees

1. **Standalone App Mode**: When installed, the app launches without browser URL bars or navigation clutter, providing a native mobile experience on iOS and Android.
2. **Zero-Private-Data Caching**: In accordance with compliance requirements, **no** authenticated report HTML, boss dashboards, employee submissions, or profile data are ever cached in Cache Storage.
3. **Safe Offline Screen**: When network connectivity is lost, navigation requests safely display a generic branded offline fallback (`/offline/`) with an automatic reconnect listener and a manual "Retry Connection" button.
4. **Origin-Root Service Worker**: The service worker is served directly from `/service-worker.js` with `Service-Worker-Allowed: /` to grant it full root scope over the application.

---

## 📁 Files & Routes Changed

| File / Route | Purpose |
| :--- | :--- |
| `/manifest.webmanifest` | Web App Manifest declaring app name, icons, start URL, theme colors, and standalone display mode. Served with MIME `application/manifest+json`. |
| `/service-worker.js` | Origin-root service worker implementing static asset caching (`gemini-updates-static-v1`) and safe `/offline/` navigation fallback. |
| `/offline/` & `templates/offline.html` | Branded, zero-private-data offline fallback page with auto-reload and retry capabilities. |
| `templates/base.html` | Integrated manifest link, mobile web app meta tags, Apple touch icons, theme colors, and service worker registration script. |
| `static/pwa/icons/*` | App icons (512x512, 192x192, 180x180 Apple touch icon, 32x32 favicon) adhering to Gemini Insights brand aesthetic. |
| `static/css/theme.css` | Touch-friendly tap target optimizations (>= 44px), viewport overflow guards, and iOS safe area padding. |
| `accounts/views.py` & `gemini_updates/urls.py` | Added Django views and root URL routes for manifest, service worker, and offline page. |
| `accounts/tests.py` | Automated unit tests covering manifest, service worker, offline fallback, and base template integration. |

---

## 💻 How to Run Locally

1. Start the Django development server:
   ```bash
   python manage.py runserver
   ```
2. Open [http://localhost:8000/](http://localhost:8000/) or [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in Google Chrome / Edge / Firefox.
3. Open **Chrome DevTools (F12)** -> **Application** tab:
   - Under **Manifest**: Verify "Gemini Insights" identity, theme color (`#111827`), and icons appear without errors.
   - Under **Service Workers**: Verify `/service-worker.js` is registered, active, and running.
   - Under **Cache Storage**: Verify `gemini-updates-static-v1` contains only static assets and `/offline/`.

> [!NOTE]
> Browsers permit Service Workers on `localhost` / `127.0.0.1` for development. In production, **HTTPS is strictly required** for service worker activation and PWA installation. (Render / standard PaaS hosting automatically provides HTTPS).

---

## 📱 How to Install on Mobile Devices

### 🤖 Android (Google Chrome / Brave / Edge)
1. Navigate to your deployed Gemini Insights URL in Chrome over HTTPS.
2. Tap the **three dots menu (⋮)** in the top-right corner.
3. Tap **"Install app"** or **"Add to Home screen"**.
4. Confirm the prompt. The "Gemini Insights" app icon will appear on your app drawer and home screen.

### 🍏 iPhone & iPad (Apple Safari)
1. Navigate to your deployed Gemini Insights URL in Safari over HTTPS.
2. Tap the **Share** button (the square with an arrow pointing upward) at the bottom toolbar.
3. Scroll down and tap **"Add to Home Screen"**.
4. Confirm by tapping **"Add"** in the top-right corner. Gemini Insights will launch in standalone full-screen mode when tapped.

---

## 🔄 How to Invalidate / Bump Cache Version

When you update CSS, JavaScript, or static assets:

1. Open `static/js/service-worker.js`.
2. Increment the cache version constant at the top of the file:
   ```javascript
   const CACHE_NAME = 'gemini-updates-static-v2'; // Bump from v1 to v2
   ```
3. Deploy the update. The service worker's `activate` event will automatically delete older cache stores (`gemini-updates-static-v1`) and download the updated static files.
