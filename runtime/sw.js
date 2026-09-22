/* TilTale service worker: lets a downloaded story open and restart without a connection
 * (see the README, "Offline classroom use"). Registered by tiltale.js on HTTPS, outside the studio.
 *
 * Strategy per request:
 * - log.php and anything not GET: never touched; the log queue in tiltale.js handles being offline.
 * - images (dist/assets/): cache first; tiltale.js and the offline page already keep them in
 *   Cache Storage, and Regenerate gives a changed image list a changed story.js.
 * - pages, code and fonts: network first, so a republished story updates as before; the cached copy
 *   of the last visit answers only when the network does not. ignoreSearch: index.html?ppn=… is index.html.
 */
"use strict";

var SHELL_CACHE = "tiltale-shell";

self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (event) { event.waitUntil(self.clients.claim()); });

function cachedFirst(request) {
  return caches.match(request, { ignoreSearch: true }).then(function (hit) {
    return hit || fetch(request);
  });
}

function networkFirst(request) {
  return fetch(request).then(function (response) {
    if (response.ok) {
      var copy = response.clone();
      caches.open(SHELL_CACHE).then(function (cache) { cache.put(request.url.split("?")[0], copy); });
    }
    return response;
  }).catch(function () {
    return caches.match(request, { ignoreSearch: true }).then(function (hit) {
      if (hit) return hit;
      throw new Error("Offline and not downloaded: " + request.url);
    });
  });
}

self.addEventListener("fetch", function (event) {
  var url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.indexOf("log.php") !== -1) return;
  var stored = url.pathname.indexOf("/assets/") !== -1;
  event.respondWith(stored ? cachedFirst(event.request) : networkFirst(event.request));
});
