const CACHE = "{{name}}-resources";
const CACHE_STATIC = "{{name}}-static-resources"

importScripts('https://storage.googleapis.com/workbox-cdn/releases/5.1.2/workbox-sw.js');

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

workbox.precaching.cleanupOutdatedCaches();

workbox.precaching.precacheAndRoute([
    {% for url in precache %}
    {
        url: '{{url}}',
        revision: null
    },
    {% endfor %}
]);

workbox.routing.registerRoute(
    ({request}) => request.destination === 'image' ||
      request.destination === 'script' ||
      request.destination === 'style',
    new workbox.strategies.CacheFirst({
      cacheName: CACHE_STATIC,
      plugins: [
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 60,
          maxAgeSeconds: 30 * 24 * 60 * 60, // 30 Days
        }),
      ],
    })
);

workbox.routing.setDefaultHandler(new workbox.strategies.StaleWhileRevalidate({
    cacheName: CACHE
}));

async function offlinePage(file) {
  const cached = await self.caches.match(file);
  if (!cached) {
      console.log('offline page not found in cache');
      return Response.error();
  }
  return cached;
}

const handler = async (event) => {
    console.log('Destination: %o', event.request.headers);
    if (event.request.headers.get('Accept').includes('application/json')) {
      return offlinePage('{{context}}/offline.json');
    }
    switch (event.request.destination) {
        case 'document':
            return offlinePage('{{context}}/offline.html');
        default:
            return Response.error();
    }
};

workbox.routing.setCatchHandler(handler);