frappe.ui.form.on("Customer", {
    setup(frm) {
        frappe.realtime.on("customer_status_updated", (data) => {
            if (frm.doc && frm.doc.name === data.customer) {
                frm.reload_doc();
            }
        });
        frappe.realtime.on("doc_update", (data) => {
            if (data && data.doctype === "Customer" && frm.doc && frm.doc.name === data.name) {
                frm.reload_doc();
            }
        });
    },

    after_save(frm) {
        frm.reload_doc();
    },

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

        // 🏷️ Status Indicator (New Customer / Old Customer)
        if (!frm.is_new() && frm.doc.customer_status) {
            const color = frm.doc.customer_status === "Old Customer" ? "blue" : "green";
            frm.page.set_indicator(__(frm.doc.customer_status), color);
        }

        frm.trigger("set_city_state");
        frm.trigger("render_location_trash_icons");

        // 🔒 Lock Opening Balance if Sales Bills (Invoices) exist
        if (!frm.is_new() && frm.doc.name) {
            frappe.db.count("Invoice", { filters: { customer_id: frm.doc.name } }).then(count => {
                if (count > 0) {
                    frm.set_df_property("opening_balance", "read_only", 1);
                    frm.set_intro(__("Customer Edit and Opening Balance is locked because Sales Bills (Invoices) exist for this customer. Updates occur automatically via transactions."), "blue");

                    // Add Opening Balance action button ONLY when Customer Opening Balance is locked
                    frm.add_custom_button(__("Add Opening Balance"), () => {
                        frm.trigger("prompt_add_opening_balance");
                    });
                } else {
                    frm.set_df_property("opening_balance", "read_only", 0);
                    frm.set_intro(null);
                }
            });
        }
    },

    prompt_add_opening_balance(frm) {
        frappe.prompt([
            {
                fieldname: "amount",
                fieldtype: "Currency",
                label: __("Opening Balance Amount to Add"),
                reqd: 1
            },
            {
                fieldname: "remarks",
                fieldtype: "Small Text",
                label: __("Remarks"),
                default: "Additional Opening Balance added"
            }
        ], function (values) {
            if (flt(values.amount) <= 0) {
                frappe.msgprint(__("Amount must be greater than 0"));
                return;
            }
            frappe.call({
                method: "company.company.api.add_customer_opening_balance",
                args: {
                    customer_id: frm.doc.name,
                    amount: values.amount,
                    remarks: values.remarks
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __("Added ₹{0} to Opening Balance", [format_currency(values.amount)]),
                            indicator: "green"
                        });
                        frm.reload_doc();
                    }
                }
            });
        }, __("Add Opening Balance"), __("Add Amount"));
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
                    frm.set_read_only();
                    frm.disable_save();
                    frm.wrapper.addClass("customer-locked-form");
                    frm.page.wrapper.addClass("customer-locked-form");
                    $(".page-head, .page-actions, body").addClass("customer-locked-form");

                    // Disable all fields
                    frm.meta.fields.forEach(df => {
                        if (df.fieldname) {
                            frm.set_df_property(df.fieldname, "read_only", 1);
                        }
                    });
                    frm.refresh_fields();

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

                    // Disable Save and hide Save button completely
                    frm.disable_save();
                    frm.page.clear_primary_action();
                    frm.page.wrapper.find(".primary-action, .btn-primary, [data-label='Save']").hide();

                    let attempts = 0;
                    let timer = setInterval(() => {
                        attempts++;
                        frm.page.clear_primary_action();
                        frm.page.wrapper.find(".primary-action, .btn-primary, [data-label='Save']").hide();
                        if (attempts > 5) clearInterval(timer);
                    }, 100);

                    // Remove all menu items
                    frm.page.clear_menu();

                    // Soft bottom alert (no popup)
                    frappe.show_alert({
                        message: __("Edit is disabled — this customer has linked Invoice / Estimation / Purchase records."),
                        indicator: "red"
                    }, 3);
                    frm._alert_shown = true;

                } else {
                    frm.wrapper.removeClass("customer-locked-form");
                    $("body").removeClass("customer-locked-form");
                    // Unlock when no links
                    frm.meta.fields.forEach(df => {
                        if (df.fieldname) {
                            frm.set_df_property(df.fieldname, "read_only", 0);
                        }
                    });

                    frm.trigger("set_city_state");

                    frm.enable_save();
                    if (frm.page.btn_primary) {
                        frm.page.btn_primary.show();
                    }
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
