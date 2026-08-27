// ===============================
// FIREBASE INITIALIZATION (v10+ compat)
// ===============================

// Step 1️⃣ - Load Firebase App first
const scriptApp = document.createElement("script");
scriptApp.src = "https://www.gstatic.com/firebasejs/10.8.1/firebase-app-compat.js";

scriptApp.onload = () => {
  console.log("🟢 Firebase App Loaded");

  // Step 2️⃣ - Load Messaging
  const scriptMsg = document.createElement("script");
  scriptMsg.src = "https://www.gstatic.com/firebasejs/10.8.1/firebase-messaging-compat.js";

  scriptMsg.onload = () => {
    console.log("🟢 Firebase Messaging Loaded");

    // Step 3️⃣ - Firebase Config
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

    if (
      "serviceWorker" in navigator &&
      "Notification" in window &&
      typeof firebase.messaging === "function" &&
      firebase.messaging.isSupported()
    ) {
      try {
        const messaging = firebase.messaging();
        console.log("✅ Firebase Messaging initialized");

        const vapidKey = frappe.boot.site_config?.firebase?.vapid_key;
        if (!vapidKey) {
          console.warn("⚠️ Firebase VAPID key not configured");
          return;
        }

        navigator.serviceWorker.ready.then((registration) => {
          Notification.requestPermission().then((permission) => {
            if (permission !== "granted") return;

            messaging
              .getToken({
                vapidKey: vapidKey,
                serviceWorkerRegistration: registration,
              })
              .then((token) => {
                if (!token) return;
                frappe.call({
                  method: "company.company.api.save_fcm_token",
                  args: { token },
                  callback: function () {
                    console.log("✅ FCM Token saved");
                  },
                });
              })
              .catch((err) => {
                console.warn("FCM Token notice:", err);
              });
          });
        });

        messaging.onMessage((payload) => {
          if (payload && payload.notification) {
            new Notification(payload.notification.title, {
              body: payload.notification.body,
              icon: "https://erp.innoblitz.in/assets/Innoblitz%20Logo%20Full.png",
            });
          }
        });
      } catch (e) {
        console.warn("Firebase messaging initialization skipped:", e);
      }
    }
  };

  document.head.appendChild(scriptMsg);
};

document.head.appendChild(scriptApp);
