frappe.after_ajax(() => {
    if (!frappe.session.user || frappe.session.user === "Guest") return;

    frappe.call({
        method: "company.company.api.get_today_checkin_time",
        callback: function (r) {
            if (!r.message) return;

            const data = r.message;
            let display = "";
            let badgeStyle = ""; // custom style per status

            switch (data.status) {
                case "Present":
                case "Checked In":
                    display = `Today Checked In: ${data.checkin_time}`;
                    badgeStyle = `
                        background-color: #e7f1ff;
                        color: #007bff;
                    `;
                    break;
                case "Absent":
                case "Not Checked In":
                    display = `Not Checked In`;
                    badgeStyle = `
                        background-color: #ffe7e7;
                        color: #ff3b3b;
                        font-weight: 600;
                    `;
                    break;
                case "Missing":
                    display = `Today Checked In: ${data.checkin_time}`;
                    badgeStyle = `
                        background-color: #e7f1ff;
                        color: #007bff;
                        font-weight: 600;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    `;
                    break;
                case "On Leave":
                    display = `On Leave`;
                    badgeStyle = `
                        background-color: #e6f7e6;
                        color: #28a745;
                        font-weight: 500;
                    `;
                    break;
                default:
                    display = `Not Linked`;
                    badgeStyle = `
                        background-color: #f0f0f0;
                        color: #6c757d;
                    `;
            }

            const interval = setInterval(() => {
                const logo = document.querySelector(".navbar .navbar-brand.navbar-home"); // ✅ target the logo
                if (logo) {
                    clearInterval(interval);

                    const badge = document.createElement("div");
                    badge.innerText = display;
                    badge.style.cssText = `
                        display: inline-flex;
                        justify-content: center;
                        align-items: center;
                        padding: 2px 12px;
                        margin-left: 12px; /* ✅ perfect spacing after logo */
                        border-radius: 14px;
                        font-size: 13px;
                        line-height: 20px;
                        white-space: nowrap;
                        ${badgeStyle}
                        transition: all 0.3s ease;
                        cursor: default;
                    `;

                    // hover effect
                    badge.addEventListener("mouseenter", () => {
                        badge.style.transform = "scale(1.05)";
                    });
                    badge.addEventListener("mouseleave", () => {
                        badge.style.transform = "scale(1)";
                    });

                    // ✅ insert right AFTER logo
                    logo.insertAdjacentElement("afterend", badge);
                }
            }, 500);
        }
    });
});

// Global listener to blur active input when hovering/touching the primary action button
$(document).on('mouseenter touchstart', '.primary-action, .btn-primary', function () {
    if (document.activeElement && (document.activeElement.tagName === "INPUT" || document.activeElement.tagName === "TEXTAREA")) {
        document.activeElement.blur();
    }
});

