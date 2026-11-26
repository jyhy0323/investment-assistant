const CACHE_NAME = "ai-stock-pwa-v1";
const STATIC_ASSETS = [
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/apple-touch-icon.png",
  "/static/icons/icon.svg"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  // API 요청과 HTML 문서는 항상 최신 데이터를 우선(Network-first)
  if (
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/macro") ||
    url.pathname.startsWith("/health") ||
    req.mode === "navigate"
  ) {
    event.respondWith(
      fetch(req).catch(() => caches.match(req))
    );
    return;
  }

  // 정적 아이콘/CSS/JS는 네트워크 우선 + 오프라인 캐시 폴백
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.status === 200 && url.pathname.startsWith("/static/")) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, clone)).catch(() => {});
        }
        return res;
      })
      .catch(() => caches.match(req))
  );
});
