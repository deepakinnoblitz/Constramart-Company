// Copyright (c) 2025, deepak and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Customer", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("Customer", {
    refresh(frm) {

        frm.trigger("lock_based_on_links");

        // ✅ Default country only for new docs
        if (frm.is_new() && !frm.doc.country) {
            frm.set_value("country", "India");
        }

        // 🔥 Always load states if country exists
        if (frm.doc.country) {
            load_states_and_restore_state(frm);
        }

        // 🔁 Load cities if state exists
        if (frm.doc.country && frm.doc.state && frm.doc.state !== "Others") {
            load_cities(frm);
        }

        // 🏷️ Status Indicator (Old/New) - Form View ONLY
        if (!frm.is_new()) {
            const label = frm.doc.is_old_customer ? __("Old") : __("New");
            const color = frm.doc.is_old_customer ? "blue" : "green";
            frm.page.set_indicator(label, color);
        }

        frm.trigger("set_city_state");
    },

    onload(frm) {
        if (!frm.is_new()) {
            const label = frm.doc.is_old_customer ? __("Old") : __("New");
            const color = frm.doc.is_old_customer ? "blue" : "green";
            frm.page.set_indicator(label, color);
        }
    },

    country(frm) {
        if (!frm.doc.country) return;

        // Reset dependent fields
        frm.set_value("state", null);
        frm.set_value("city", null);

        frm.trigger("set_city_state");

        load_states_and_restore_state(frm);
    },

    state(frm) {
        frm.trigger("set_city_state");

        if (!frm.doc.state) return;

        if (frm.doc.state === "Others") {
            frm.set_df_property("city", "options", "Others");
            frm.refresh_field("city");
            return;
        }

        load_cities(frm);
    },

    lock_based_on_links(frm) {
        if (!frm.doc.name) return;

        frappe.call({
            method: "company.company.api.check_customer_links",
            args: { customer: frm.doc.name },
            callback: function (r) {
                let has_links = r.message || false;

                if (has_links) {

                    // Disable all fields
                    frm.fields.forEach(f => {
                        if (f.df.fieldname) {
                            frm.set_df_property(f.df.fieldname, "read_only", 1);
                        }
                    });

                    // Disable child tables
                    frm.meta.fields.forEach(df => {
                        if (df.fieldtype === "Table") {
                            frm.get_field(df.fieldname).grid.toggle_enable(false);
                        }
                    });

                    // Disable Save
                    frm.disable_save();

                    // Remove all menu items
                    frm.page.clear_menu();

                    // Soft bottom alert (no popup)
                    frappe.show_alert({
                        message: __("Edit is disabled — this customer has linked Invoice / Estimation / Purchase records."),
                        indicator: "red"
                    }, 3);
                    frm._alert_shown = true;

                } else {
                    // Unlock when no links
                    frm.fields.forEach(f => {
                        if (f.df.fieldname) {
                            frm.set_df_property(f.df.fieldname, "read_only", 0);
                        }
                    });

                    frm.trigger("set_city_state");

                    frm.enable_save();
                }
            }
        });
    },

    set_city_state(frm) {
        let is_locked = false;
        if (!frm.is_new()) {
            let field = frm.get_field("customer_name");
            if (field && field.df.read_only) {
                is_locked = true;
            }
        }
        frm.set_df_property("city", "read_only", (frm.doc.state && !is_locked) ? 0 : 1);
    }

});

function load_states_and_restore_state(frm) {
    const existing_state = frm.doc.state;

    frappe.call({
        method: "company.company.api.get_states",
        args: { country: frm.doc.country },
        callback(r) {
            const states = ["", ...(r.message || []), "Others"];

            frm.set_df_property("state", "options", states.join("\n"));
            frm.refresh_field("state");

            // ✅ Restore state AFTER options exist
            if (existing_state && states.includes(existing_state)) {
                frm.set_value("state", existing_state);
            }
        }
    });
}

function load_cities(frm) {
    const existing_city = frm.doc.city;

    frappe.call({
        method: "company.company.api.get_cities",
        args: {
            country: frm.doc.country,
            state: frm.doc.state
        },
        callback(r) {
            const cities = ["", ...(r.message || []), "Others"];

            frm.set_df_property("city", "options", cities.join("\n"));
            frm.refresh_field("city");

            // ✅ Restore city AFTER options exist
            if (existing_city && cities.includes(existing_city)) {
                frm.set_value("city", existing_city);
            }
        }
    });
}
