frappe.ui.form.on("Customer", {
    refresh(frm) {
        // if (!frm.is_new()) {
        //     frm.page.add_inner_button(__("Refresh Old Status"), () => {
        //         frappe.call({
        //             method: "company.company.doctype.invoice.invoice.refresh_customer_status",
        //             args: { customer: frm.doc.name },
        //             callback: function(r) {
        //                 if(r.message) {
        //                     frappe.show_alert({message: __("Status Refreshed Successfully!"), indicator: "green"});
        //                     frm.reload_doc();
        //                 }
        //             }
        //         });
        //     });
        // }

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
        frm.trigger("render_location_trash_icons");
    },

    render_location_trash_icons(frm) {
        const grid = frm.get_field("location").grid;
        // Small delay to ensure grid is fully rendered
        setTimeout(() => {
            grid.wrapper.find(".grid-row").each(function () {
                const $row = $(this);
                const name = $row.attr("data-name");
                if (!name || name === "new-row" || name.startsWith("new-customer-location")) return;

                // Find the action column (where pencil is)
                const action_area = $row.find(".btn-open-row").parent();
                if (action_area.length && !$row.find(".custom-grid-delete").length) {
                    const $trash = $(`
                        <a class="custom-grid-delete" title="Delete Location" style="
                            margin-left: 10px; cursor: pointer; color: #d63232;
                            display: inline-flex; vertical-align: middle; padding: 3px; border-radius: 4px;
                        ">
                            <svg class="icon icon-sm" style="width: 14px; height: 14px; fill: none; stroke: currentColor; stroke-width: 2;"><use href="#icon-delete"></use></svg>
                        </a>
                    `);

                    $trash.on("click", (e) => {
                        e.preventDefault(); e.stopPropagation();
                        console.log("Trash icon clicked for row:", name);
                        if (frm.events.handle_custom_location_delete) {
                            frm.events.handle_custom_location_delete(frm, name);
                        } else {
                            // Fallback to trigger
                            frm.trigger("handle_custom_location_delete", name);
                        }
                    });

                    action_area.append($trash);
                }
            });
        }, 300);
    },

    handle_custom_location_delete(frm, row_name) {
        const row = locals["Customer Location"][row_name];
        if (!row) return;

        frappe.confirm(
            __("Are you sure you want to permanently delete location '<b>{0}</b>'?<br><br>This will check for linked Invoices before deleting.", [row.location_name]),
            () => {
                frappe.call({
                    method: "company.company.api.delete_customer_location",
                    args: { row_name: row_name },
                    callback: function (r) {
                        if (r.message && r.message.status === "success") {
                            frappe.show_alert({ message: __("Location deleted"), indicator: "green" });
                            frm.reload_doc();
                        } else if (r.message && r.message.status === "error") {
                            frappe.msgprint({ title: __("Cannot Delete"), message: r.message.message, indicator: "red" });
                        }
                    }
                });
            }
        );
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
                            const field = frm.get_field(df.fieldname);
                            if (df.fieldname === "location") {
                                // Enable grid but restrict actions
                                field.grid.toggle_enable(true);
                                field.grid.cannot_add_rows = true;
                                
                                // Hide the 'Add Row' button even if it's enabled
                                field.grid.wrapper.find(".grid-add-row").hide();
                                
                                // Hide the Pencil icon (Edit) to ensure 'Delete Only' 
                                // Modern Frappe uses .btn-open-row for the detail view button
                                if (!$('#customer-locked-grid-css').length) {
                                    $(`<style id="customer-locked-grid-css">
                                        .locked-location-grid .btn-open-row { display: none !important; }
                                        .locked-location-grid .grid-static-col .octicon-pencil { display: none !important; }
                                    </style>`).appendTo('head');
                                }
                                field.grid.wrapper.addClass('locked-location-grid');

                                // Make row fields read-only
                                field.grid.docfields.forEach(docf => {
                                    frm.set_df_property(docf.fieldname, "read_only", 1, frm.doc.name, df.fieldname);
                                });
                            } else {
                                field.grid.toggle_enable(false);
                            }
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

// === Location Deletion Sync ===
frappe.ui.form.on("Customer Location", {
    location_on_grid_refresh: function (frm) {
        frm.trigger("render_location_trash_icons");
    },
    before_location_remove: function (frm, cdt, cdn) {
        // Only override if the main form is locked (links exist)
        let is_locked = !frm.is_save_allowed() || (frm.get_field("customer_name")?.df.read_only && !frm.is_new());
        if (!is_locked) return;

        let row = locals[cdt][cdn];
        
        // If it's a new row not yet saved, allow standard Frappe deletion
        if (!row || !row.name || row.name.startsWith("new-customer-location")) return;

        // Permanent deletion from database
        frappe.confirm(
            __("Are you sure you want to permanently delete location '<b>{0}</b>'?<br><br>This will check for linked Invoices before deleting.", [row.location_name]),
            () => {
                frappe.call({
                    method: "company.company.company.api.delete_customer_location",
                    args: { row_name: row.name },
                    btn: $('.locked-location-grid .grid-row[data-name="' + row.name + '"] .grid-static-col .octicon-trash'),
                    callback: function (r) {
                        if (r.message && r.message.status === "success") {
                            frappe.show_alert({ message: __("Location deleted successfully"), indicator: "green" });
                            frm.reload_doc();
                        } else if (r.message && r.message.status === "error") {
                            frappe.msgprint({
                                title: __("Cannot Delete"),
                                message: r.message.message,
                                indicator: "red"
                            });
                            frm.reload_doc();
                        }
                    }
                });
            },
            () => {
                // On Cancel: Reload to restore the row in UI
                frm.reload_doc();
            }
        );

        // Return false to prevent standard Frappe row removal (which requires a Save click)
        return false;
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
