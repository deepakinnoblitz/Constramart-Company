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
        // Use set_query with dynamic doc evaluation for grid filters
        frm.set_query("tax_type", "table_qecz", function (doc, cdt, cdn) {
            if (doc.default_tax_type === "Exempted") {
                return {
                    filters: {
                        "name": "Exempted"
                    }
                };
            } else if (doc.default_tax_type) {
                return {
                    filters: {
                        "name": ["!=", "Exempted"]
                    }
                };
            }
            return {};
        });

        // SMART LIVE REFRESH: Instantly commit empty values when cleared
        // This ensures the parent updates exactly when the text is cleared, without needing blur
        frm.fields_dict.table_qecz.grid.wrapper.on("input",
            'input[data-fieldname="service"], input[data-fieldname="tax_type"]',
            function () {
                let val = $(this).val();
                if (!val) {
                    let $row = $(this).closest('.grid-row');
                    let docname = $row.attr('data-name');
                    if (docname) {
                        let item = locals["Purchase Items"][docname];
                        let fieldname = $(this).attr("data-fieldname");
                        // If model still has value, clear it immediately
                        if (item && item[fieldname]) {
                            frappe.model.set_value(item.doctype, item.name, fieldname, "");
                        }
                    }
                }
            }
        );

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
                console.log('balance amount : ' + frm.doc.balance_amount);
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
        let item = locals[cdt][cdn];

        if (item.tax_type) {
            frm.set_value("default_tax_type", item.tax_type);
        } else {
            // Check if ANY other row has a tax_type
            let other_tax = (frm.doc.table_qecz || []).find(d => d.tax_type);
            if (!other_tax) {
                frm.set_value("default_tax_type", "");
            }

            setTimeout(() => {
                if (document.activeElement && document.activeElement.blur) {
                    document.activeElement.blur();
                }
            }, 10);
        }
        frm.refresh_field("table_qecz");
    }
});