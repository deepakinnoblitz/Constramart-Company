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

        // Watch for changes (sidebar appearing later)
        // Disconnect after successful injection could be an option, but 
        // sidebar might be re-rendered (e.g. partial reload). 
        // We keeping it but strictly checking for existence.
        const observer = new MutationObserver((mutations) => {
            if (!document.querySelector("#company-sidebar-logo")) {
                injectLogo();
            }
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
