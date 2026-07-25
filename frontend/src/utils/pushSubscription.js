// Utility to convert VAPID base64 public key to Uint8Array for pushManager
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/\-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export async function registerServiceWorkerAndSubscribePush() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    console.warn('Web Push Notifikasi tidak didukung oleh browser ini.');
    return false;
  }

  try {
    // 1. Register Service Worker
    const registration = await navigator.serviceWorker.register('/service-worker.js');
    await navigator.serviceWorker.ready;

    // 2. Request Notification Permission
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      console.info('Izin notifikasi Web Push ditolak oleh pengguna.');
      return false;
    }

    // 3. Fetch VAPID Public Key from Backend
    const res = await fetch('http://localhost:8000/api/v1/notifications/vapid-public-key');
    if (!res.ok) throw new Error('Gagal mengambil VAPID Public Key');
    const { public_key } = await res.json();

    if (!public_key) {
      console.warn('VAPID Public Key belum dikonfigurasi di server.');
      return false;
    }

    const applicationServerKey = urlBase64ToUint8Array(public_key);

    // 4. Subscribe to Push Manager
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationServerKey
      });
    }

    const token = localStorage.getItem('token') || localStorage.getItem('access_token');
    if (!token) return true;

    // 5. Send subscription info to backend API
    const subJson = subscription.toJSON();
    await fetch('http://localhost:8000/api/v1/notifications/subscribe-push', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({
        endpoint: subJson.endpoint,
        keys: subJson.keys
      })
    });

    console.log('✅ Web Push Subscription berhasil didaftarkan ke TEIS Backend.');
    return true;
  } catch (err) {
    console.error('Error saat mendaftarkan Web Push subscription:', err);
    return false;
  }
}
