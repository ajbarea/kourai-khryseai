/* Kourai Khryseai — The Forge · service worker
 * Bump VERSION on any asset change to invalidate the old cache. */
const VERSION = "kk-forge-v3";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./assets/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(VERSION).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  // Navigation: network-first so updates land, fall back to cached shell offline.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => { const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy)); return res; })
        .catch(() => caches.match(req).then((c) => c || caches.match("./index.html")))
    );
    return;
  }

  // Static assets: cache-first, then network (and cache same-origin responses).
  event.respondWith(
    caches.match(req).then((cached) =>
      cached || fetch(req).then((res) => {
        if (res.ok && new URL(req.url).origin === self.location.origin) {
          const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy));
        }
        return res;
      })
    )
  );
});
