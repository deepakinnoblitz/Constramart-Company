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
    const messaging = firebase.messaging();

    console.log("✅ Firebase initialized");

    // Step 4️⃣ - Wait for Service Worker
    navigator.serviceWorker.ready.then((registration) => {
      console.log("🟢 SW Ready:", registration);

      // Step 5️⃣ - Notification permission
      Notification.requestPermission().then((permission) => {
        console.log("🔹 Permission:", permission);

        if (permission !== "granted") {
          console.warn("🚫 Notification permission denied");
          return;
        }

        // Step 6️⃣ - Get FCM token — this links messaging → SW automatically
        messaging
          .getToken({
            vapidKey: frappe.boot.site_config.firebase.vapid_key,
            serviceWorkerRegistration: registration, // ✔ Correct way in v10
          })
          .then((token) => {
            if (!token) {
              console.warn("⚠️ No token received");
              return;
            }

            console.log("🔥 FCM Token:", token);

            // Step 7️⃣ - Save token to backend
            frappe.call({
              method: "company.company.api.save_fcm_token",
              args: { token },
              callback: function () {
                console.log("✅ Token saved");
              },
            });
          })
          .catch((err) => {
            console.error("❌ Token error:", err);
          });
      });
    });

    messaging.onMessage((payload) => {
      console.log("🔔 Foreground Message:", payload);

      // Browser notification
      new Notification(payload.notification.title, {
        body: payload.notification.body,
        icon: "https://erp.innoblitz.in/assets/Innoblitz%20Logo%20Full.png",
      });
    });
  };

  document.head.appendChild(scriptMsg);
};

document.head.appendChild(scriptApp);
