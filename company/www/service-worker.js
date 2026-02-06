importScripts("https://www.gstatic.com/firebasejs/10.8.1/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.8.1/firebase-messaging-compat.js");

// ===============================
// ✅ FIREBASE INITIALIZATION
// ===============================
const firebaseConfig = {
    apiKey: "AIzaSyAp3cIYT8C4gRD_vliPK0PODHzyyyFYu4Y",
    authDomain: "company-erp-ef845.firebaseapp.com",
    projectId: "company-erp-ef845",
    storageBucket: "company-erp-ef845.firebasestorage.app",
    messagingSenderId: "695314443067",
    appId: "1:695314443067:web:07f8f463a526660a7e251e",
    measurementId: "G-ZDGX26G2EW",
};

firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

console.log("🔥 [Service Worker] Firebase Initialized & Background Handler Ready");

// ✅ Handle Background Notifications
messaging.onBackgroundMessage((payload) => {
    console.log("🔥 [Service Worker] Received background message:", payload);

    const notificationTitle = payload.notification.title;
    const notificationOptions = {
        body: payload.notification.body,
        icon: "https://erp.innoblitz.in/assets/Innoblitz%20Logo%20Full.png", // Customize this icon path
        badge: "https://erp.innoblitz.in/assets/Innoblitz%20Logo%20Full.png", // Customize this badge path
        data: payload.data, // Pass data for click handling
    };

    self.registration.showNotification(notificationTitle, notificationOptions);
});

// ===============================
// 🌐 PWA CACHING LOGIC
// ===============================

self.addEventListener("install", event => {
    event.waitUntil(
        caches.open("erpnext-cache-v1").then(cache => {
            // Try to cache core assets, but don't fail installation if one fails
            return cache.addAll([
                "/",
            ]).catch(err => {
                console.warn("⚠️ Failed to cache some assets, but Service Worker is still installed:", err);
            });
        })
    );
});

self.addEventListener("fetch", event => {
    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});

// ✅ Notification Click Handler (Optional but recommended)
self.addEventListener("notificationclick", (event) => {
    event.notification.close();

    const targetUrl = event.notification.data?.url || "/app";

    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true })
            .then((clientList) => {
                for (const client of clientList) {
                    // If the tab already exists, focus it and navigate
                    if ("focus" in client) {
                        client.focus();
                        client.navigate(targetUrl);
                        return;
                    }
                }
                // No open tab → open new one
                return clients.openWindow(targetUrl);
            })
    );
});

