// Service worker Finn: interfața merge și offline (datele vin mereu proaspete de la server).
const CACHE = "finn-v6";
const SHELL = ["/", "/static/styles.css", "/static/i18n.js", "/static/icons.js", "/static/finn.js", "/static/charts.js", "/static/story.js",
  "/static/app.js", "/static/icons/icon.svg", "/static/icons/icon-192.png", "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return; // API-ul nu se cachează
  // network-first: versiunea nouă când ești online, cea salvată când nu
  e.respondWith(fetch(e.request).then((res) => {
    if (res.ok && url.origin === location.origin) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
    return res;
  }).catch(() => caches.match(e.request)));
});
