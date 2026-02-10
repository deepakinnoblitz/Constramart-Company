frappe.ui.form.on("Service", {
    // When form loads
    refresh(frm) {
        // 🚀 SILENCE: Hide the hard error dialog container
        if (!$('#silence-service-dialog').length) {
            $('<style id="silence-service-dialog">#dialog-container { display: none !important; }</style>').appendTo('head');
        }

        // Live update as user types (provides immediate visual feedback and ensuring title is set for Quick Entry)
        if (frm.fields_dict.service_name) {
            frm.fields_dict.service_name.$input.on('input', () => {
                let val = frm.fields_dict.service_name.get_value();
                frm.set_value("service_name_title", val);
            });
        }
    },

    // When the field changes (e.g. on blur or Enter)
    service_name(frm) {
        if (frm.doc.service_name) {
            frm.set_value("service_name_title", frm.doc.service_name);
        }
    },

    validate(frm) {
        // Prevent the invisible "Duplicate Name" dialog from blocking the UI
        if (frm.is_new() && frm.doc.service_name) {
            return frappe.db.exists("Service", frm.doc.service_name).then(exists => {
                if (exists) {
                    frappe.show_alert({
                        message: __("Service '{0}' already exists", [frm.doc.service_name]),
                        indicator: "orange"
                    });
                    frappe.validated = false;
                }
            });
        }
    },

    // 🔁 Rename ONLY after save is successful
    after_save(frm) {
        // Show custom success message since standard ones are hidden
        show_custom_service_toast(__("Saved Successfully"), "green");

        // Only rename if it's an existing record and the name doesn't match the Service Name
        if (!frm.is_new() && frm.doc.service_name && frm.doc.name !== frm.doc.service_name) {
            frappe.call({
                method: "company.company.doctype.service.service.rename_service",
                args: {
                    docname: frm.doc.name,
                    new_title: frm.doc.service_name
                },
                callback: function (r) {
                    if (r.message && r.message !== frm.doc.name) {
                        // Refresh form with new name
                        frappe.set_route("Form", frm.doctype, r.message);
                    }
                }
            });
        }
    }
});

/**
 * Custom toast notification for Service DocType
 * Bypasses the hidden #alert-container/dialog-container
 */
function show_custom_service_toast(msg, type) {
    const is_green = type === "green";
    const bg = is_green ? "#e2f6ec" : "#fff5e6";
    const color = is_green ? "#28a745" : "#ffc107";
    const border = is_green ? "#ade3c8" : "#ffe5cc";
    const icon = is_green ? "fa-check-circle" : "fa-exclamation-triangle";

    const toast = $(`
        <div class="custom-service-toast" style="
            position: fixed;
            bottom: 40px;
            right: 40px;
            padding: 14px 24px;
            background: ${bg};
            color: ${color};
            border: 1px solid ${border};
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            z-index: 100001;
            font-size: 14px;
            display: none;
            align-items: center;
            gap: 10px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        ">
            <i class="fa ${icon}" style="font-size: 16px;"></i>
            <span>${msg}</span>
        </div>
    `).appendTo('body');

    toast.css('display', 'flex').hide().fadeIn(300).delay(2500).fadeOut(500, function () {
        $(this).remove();
    });
}
