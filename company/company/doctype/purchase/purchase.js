// Copyright (c) 2025, deepak and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase", {
    onload(frm) {
        if (frm.is_new() && (!frm.doc.table_qecz || frm.doc.table_qecz.length === 0)) {
            frm.add_child("table_qecz");
            frm.refresh_field("table_qecz");
        }
    },
    refresh(frm) {

        // Filter Vendor ID to only show Customers with customer_type = 'Purchase'
        frm.set_query("vendor_id", function () {
            return {
                filters: {
                    customer_type: "Purchase"
                }
            };
        });

        // Lock form if collections exist
        if (!frm.is_new()) {
            frappe.db.count("Purchase Collection", { filters: { purchase: frm.doc.name } }).then(count => {
                if (count > 0) {
                    frm.set_read_only();
                    frm.disable_save();
                    frm.set_intro(
                        __("This Purchase is {0} because {1} Payment Collection(s) have been recorded. To edit this Purchase, please delete the linked collections first.",
                            ["<b class='text-danger'>Locked</b>", "<b>" + count + "</b>"]),
                        "red"
                    );

                    // Hide "Not Saved" indicator to avoid confusion
                    $(".indicator-pill:contains('Not Saved')").hide();
                }
            });

            // Collection Management Buttons
            if (flt(frm.doc.balance_amount, 2) > 0) {
                frm.add_custom_button(__("Create Collection"), function () {
                    frappe.new_doc("Purchase Collection", {
                        purchase: frm.doc.name,
                        vendor_id: frm.doc.vendor_id,
                        vendor_name: frm.doc.vendor_name,
                        business_person: frm.doc.business_person_name,
                        amount_to_pay: frm.doc.balance_amount,
                        payment_date: frappe.datetime.get_today()
                    });
                }, __("Collections"));
            }

            frm.add_custom_button(__("View Collections"), function () {
                frappe.set_route("List", "Purchase Collection", {
                    "purchase": frm.doc.name
                });
            }, __("Collections"));
        }
    },
    table_qecz_remove(frm) {
        setTimeout(() => {
            if (window.purchase_calculate_totals_live) {
                window.purchase_calculate_totals_live(frm);
            }
        }, 200);
    },
    // Tax auto-fill logic
    default_tax_type(frm) {
        if (!frm.doc.default_tax_type) return;

        // Get the selected tax type name
        frappe.db.get_value("Tax Types", frm.doc.default_tax_type, "name", (r) => {
            if (r && r.name === "Exempted") {
                // Auto-fill all items with "Exempted"
                frm.doc.table_qecz.forEach((item) => {
                    frappe.model.set_value(item.doctype, item.name, "tax_type", "Exempted");
                });
                frm.refresh_field("table_qecz");
            }
        });
    }
});

// Purchase Items child table logic
frappe.ui.form.on("Purchase Items", {
    before_table_qecz_add(frm, cdt, cdn) {
        // Apply default tax when adding new row
        if (frm.doc.default_tax_type) {
            frappe.db.get_value("Tax Types", frm.doc.default_tax_type, "name", (r) => {
                if (r && r.name === "Exempted") {
                    // Will be set after row is added
                    setTimeout(() => {
                        let items = frm.doc.table_qecz;
                        if (items && items.length > 0) {
                            let last_item = items[items.length - 1];
                            frappe.model.set_value(last_item.doctype, last_item.name, "tax_type", "Exempted");
                        }
                    }, 100);
                }
            });
        }
    },

    tax_type(frm, cdt, cdn) {
        // Filter dropdown in other items based on selection
        let item = locals[cdt][cdn];

        if (item.tax_type && item.tax_type !== "Exempted") {
            // Non-exempted tax selected, set as default and filter dropdowns
            frm.set_value("default_tax_type", item.tax_type);

            // Set filter for all item tax_type fields to exclude "Exempted"
            frm.fields_dict.table_qecz.grid.update_docfield_property(
                "tax_type",
                "get_query",
                function () {
                    return {
                        filters: {
                            "name": ["!=", "Exempted"]
                        }
                    };
                }
            );
            frm.refresh_field("table_qecz");
        } else if (item.tax_type === "Exempted") {
            // Exempted selected, set as default and filter to show ONLY Exempted
            frm.set_value("default_tax_type", "Exempted");

            // Set filter to show only "Exempted"
            frm.fields_dict.table_qecz.grid.update_docfield_property(
                "tax_type",
                "get_query",
                function () {
                    return {
                        filters: {
                            "name": "Exempted"
                        }
                    };
                }
            );
            frm.refresh_field("table_qecz");
        } else {
            // Tax cleared/unselected - reset filter to show all options
            frm.set_value("default_tax_type", "");

            // Remove all filters - show all tax types
            frm.fields_dict.table_qecz.grid.update_docfield_property(
                "tax_type",
                "get_query",
                function () {
                    return {};
                }
            );
            frm.refresh_field("table_qecz");
        }
    }
});
