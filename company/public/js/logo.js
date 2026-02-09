frappe.after_ajax(() => {
    try {
        // Safety check for user object
        if (!frappe.boot || !frappe.boot.user) return;

        const logged_user = frappe.boot.user.email;
        const is_admin = ["admin@example.com"].includes(logged_user);

        if (is_admin) return;

        // Hide App Switcher for non-admin users
        if (!document.querySelector("#hide-app-switcher-css")) {
            $(`<style id="hide-app-switcher-css">
                .app-switcher-dropdown {
                    display: none !important;
                }
            </style>`).appendTo("head");
        }

        // Function to inject logo
        const injectLogo = () => {
            const sidebarTop = document.querySelector(".body-sidebar-top");
            // Only inject if sidebar exists and logo doesn't
            if (sidebarTop && !document.querySelector("#company-sidebar-logo")) {
                let logo = document.createElement("div");
                logo.id = "company-sidebar-logo";
                logo.innerHTML = `
                    <img src="/assets/Innoblitz%20Logo%20Full.png"
                    style="width:165px; margin-left: 30px; display:block;">

                `;
                sidebarTop.prepend(logo);
            }
        };

        // Run immediately
        injectLogo();

        // 1. Hook into router change (Primary trigger)
        frappe.router.on('change', injectLogo);

        // 2. Debounced MutationObserver (Backup for dynamic updates)
        let timeout;
        const observer = new MutationObserver((mutations) => {
            if (timeout) clearTimeout(timeout);
            timeout = setTimeout(() => {
                if (!document.querySelector("#company-sidebar-logo")) {
                    injectLogo();
                }
            }, 500); // 500ms debounce
        });

        // Observe only the layout container if possible, otherwise body is fine but resource intensive
        const target = document.querySelector('.layout-main-section') || document.body;
        observer.observe(target, {
            childList: true,
            subtree: true
        });

    } catch (e) {
        console.error("Error in logo.js:", e);
    }
});
