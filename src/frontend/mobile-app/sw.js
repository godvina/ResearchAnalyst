// Service Worker — caches everything for offline use
const CACHE_NAME = 'ancient-mysteries-v1';
const ASSETS = [
  '/',
  '/index.html',
  '/app-data.js',
  '/audio/brief_dagda.mp3',
  '/audio/brief_aengus_og.mp3',
  '/audio/brief_nuada.mp3',
  '/audio/brief_lugh.mp3',
  '/audio/brief_brigid.mp3',
  '/audio/brief_morrigan.mp3',
  '/audio/brief_manannan_mac_lir.mp3',
  '/audio/brief_dian_cecht.mp3',
  '/audio/brief_boann.mp3',
  '/audio/brief_medb.mp3',
  '/audio/brief_tuatha_de_danann.mp3',
  '/audio/brief_balor.mp3',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS)));
});

self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    ))
  );
});
