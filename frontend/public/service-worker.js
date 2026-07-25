// TEIS Multi-Channel Notification Service Worker
// Listens for push events from OS/browser push manager and displays native notifications.

self.addEventListener('push', function(event) {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { body: event.data.text() };
    }
  }

  const title = data.title || 'TEIS Notification';
  const options = {
    body: data.body || 'Ada pemberitahuan baru dari sistem TEIS.',
    icon: '/favicon.ico',
    badge: '/favicon.ico',
    data: {
      url: data.url || '/journal',
      id: data.id,
      reference_id: data.reference_id,
      type: data.type
    },
    vibrate: [200, 100, 200],
    tag: data.id || 'teis-alert',
    renotify: true,
    actions: [
      { action: 'open', title: 'Buka TEIS Journal' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();

  const targetUrl = (event.notification.data && event.notification.data.url) ? event.notification.data.url : '/journal';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (let i = 0; i < clientList.length; i++) {
        let client = clientList[i];
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
