const CACHE_NAME = 'gkbj-pastoral-care-v1';
const urlsToCache = [
  '/',
  '/dashboard',
  '/members', 
  '/analytics',
  '/static/js/bundle.js',
  '/static/css/main.css',
  '/manifest.json'
];

// Install Service Worker
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

// Serve cached content when offline
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Cache hit - return response
        if (response) {
          return response;
        }

        return fetch(event.request).then(
          (response) => {
            // Check if we received a valid response
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }

            // Clone the response
            const responseToCache = response.clone();

            caches.open(CACHE_NAME)
              .then((cache) => {
                cache.put(event.request, responseToCache);
              });

            return response;
          }
        );
      })
  );
});

// Background sync for offline forms
self.addEventListener('sync', (event) => {
  if (event.tag === 'care-event-sync') {
    event.waitUntil(syncCareEvents());
  }
});

async function syncCareEvents() {
  try {
    // Get queued care events from IndexedDB
    const db = await openIndexedDB();
    const transaction = db.transaction(['queuedEvents'], 'readonly');
    const store = transaction.objectStore('queuedEvents');
    const events = await getAll(store);

    // Sync each queued event
    for (const event of events) {
      try {
        const response = await fetch('/api/care-events', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': event.auth_header
          },
          body: JSON.stringify(event.data)
        });

        if (response.ok) {
          // Remove from queue on success
          const deleteTransaction = db.transaction(['queuedEvents'], 'readwrite');
          const deleteStore = deleteTransaction.objectStore('queuedEvents');
          deleteStore.delete(event.id);
        }
      } catch (error) {
        console.error('Failed to sync event:', error);
      }
    }
  } catch (error) {
    console.error('Background sync failed:', error);
  }
}

// Helper function to open IndexedDB
function openIndexedDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('GKBJPastoralCare', 1);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      
      // Create stores for offline functionality
      if (!db.objectStoreNames.contains('members')) {
        db.createObjectStore('members', { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains('queuedEvents')) {
        db.createObjectStore('queuedEvents', { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains('photos')) {
        db.createObjectStore('photos', { keyPath: 'memberId' });
      }
    };
  });
}

function getAll(store) {
  return new Promise((resolve, reject) => {
    const request = store.getAll();
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}