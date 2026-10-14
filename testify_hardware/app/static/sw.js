// Service worker: interfața se deschide instant și funcționează și cu semnal slab.
// Datele (/api) vin mereu de la server, ca cifrele să fie la zi.
const CACHE = "testify-v1";
const SHELL = [
  "/static/index.html", "/static/styles.css", "/static/app.js", "/static/logo.svg",
  "/static/vendor/chart.umd.min.js", "/static/manifest.webmanifest",
  "/static/icons/icon-192.png", "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// Întâi rețeaua (ca să apară imediat versiunile noi), iar fără rețea, copia salvată.
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || !url.pathname.startsWith("/static/")) return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request)),
  );
});
