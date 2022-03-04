const CACHE = "cache-{{name}}";

importScripts('https://storage.googleapis.com/workbox-cdn/releases/5.1.2/workbox-sw.js');

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener('install', event => {
    event.waitUntil(
        self.caches.open('{{name}}-offline-fallbacks')
        .then(cache => cache.add('{{context}}/offline/index.html'))
    );
});

workbox.precaching.precacheAndRoute([
    {% for url in precache %}
    {
        url: '{{url|expand_str}}',
        revision: null
    },
    {% endfor %}
]);

workbox.routing.registerRoute(
    ({request}) => request.destination === 'image',
    new workbox.strategies.CacheFirst({
      cacheName: 'images',
      plugins: [
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 60,
          maxAgeSeconds: 30 * 24 * 60 * 60, // 30 Days
        }),
      ],
    })
);

workbox.routing.registerRoute(
    ({request}) => request.destination === 'script' ||
                    request.destination === 'style',
    new workbox.strategies.StaleWhileRevalidate({
      cacheName: 'static-resources',
    })
);

workbox.routing.setDefaultHandler(new workbox.strategies.StaleWhileRevalidate({
    cacheName: CACHE
}));

async function offlinePage(cache) {
    const cached = await cache.match('{{context}}/offline/index.html'); 
    if (!cached) {
        console.log('offline page not found in cache');
        return Response.error();
    }
    return cached;
}

const handler = async (event) => {
    console.log(`Destination: ${event.request.destination}`);
    const cache = await self.caches.open('{{name}}-offline-fallbacks');
    switch (event.request.destination) {
        case 'document':
            return offlinePage(cache);
        default:
            return Response.error();
    }
};

workbox.routing.setCatchHandler(handler);