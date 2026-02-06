// Copyright (c) 2026, deepak and contributors
// For license information, please see license.txt

frappe.ui.form.on("Business Person", {
    onload_post_render(frm) {
        // Ensure phone field is properly initialized in Quick Entry
        if (frm.fields_dict.phone_number) {
            const phone_field = frm.fields_dict.phone_number;

            // Force re-render of phone field to initialize intl-tel-input
            if (phone_field.$input && phone_field.$input.length) {
                // Trigger Frappe's phone field setup
                setTimeout(() => {
                    phone_field.refresh();

                    // If the field still doesn't have the phone widget, manually initialize it
                    if (!phone_field.$input.parent().find('.iti').length) {
                        // Re-make the field to trigger proper initialization
                        phone_field.make_input();
                    }
                }, 100);
            }
        }
    },

    refresh(frm) {

    },

    validate(frm) {
        // Check if phone number is unique
        if (frm.doc.phone_number) {
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Business Person",
                    filters: {
                        phone_number: frm.doc.phone_number,
                        name: ["!=", frm.doc.name]
                    },
                    fields: ["name"]
                },
                async: false,
                callback: function (r) {
                    if (r.message && r.message.length > 0) {
                        frappe.msgprint(__("Phone Number {0} already exists for {1}",
                            [frm.doc.phone_number, r.message[0].name]));
                        frappe.validated = false;
                    }
                }
            });
        }
    }
});
