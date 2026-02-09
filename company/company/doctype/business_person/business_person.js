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

    }
});

// Explicit listener for Quick Entry Modal
$(document).on('shown.bs.modal', function (e) {
    if (cur_dialog && cur_dialog.doctype === "Business Person") {
        bind_quick_entry_save(cur_dialog);
    }
});

function bind_quick_entry_save(dialog) {
    let original_action = dialog.primary_action;

    dialog.set_primary_action(__("Save"), function () {
        // Disable button to prevent multiple clicks
        dialog.get_primary_btn().prop('disabled', true);

        check_duplicate_async(dialog).then((is_duplicate) => {
            if (is_duplicate) {
                // If duplicate, re-enable so they can fix and try again
                dialog.get_primary_btn().prop('disabled', false);
            } else {
                // If unique, proceed with original save
                if (original_action) {
                    original_action();
                }
            }
        });
    });
}

function check_duplicate_async(dialog) {
    return new Promise((resolve) => {
        let phone = dialog.get_value("phone_number");
        let name = dialog.get_value("business_person_name");

        // Check Name
        if (name) {
            frappe.db.get_value("Business Person", {
                "business_person_name": name,
                "name": ["!=", dialog.doc.name || ""]
            }, "name").then((r) => {
                if (r && r.message && r.message.name) {
                    frappe.msgprint(__("Business Person Name '{0}' already exists.", [name]));
                    resolve(true);
                    return;
                }
                // Check Phone (nested)
                check_phone(phone, dialog, resolve);
            });
        } else {
            check_phone(phone, dialog, resolve);
        }
    });
}

function check_phone(phone, dialog, resolve) {
    if (!phone) { resolve(false); return; }
    frappe.db.get_value("Business Person", {
        "phone_number": phone,
        "name": ["!=", dialog.doc.name || ""]
    }, "name").then((r) => {
        if (r && r.message && r.message.name) {
            frappe.msgprint(__("Phone Number '{0}' already exists.", [phone]));
            resolve(true);
        } else {
            resolve(false);
        }
    });
}
