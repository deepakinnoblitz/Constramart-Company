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

        // Filter Invoice ID to only show unlinked Invoices
        frm.set_query("invoice_id", function () {
            return {
                query: "company.company.api.get_unlinked_invoices"
            };
        });

        // Lock Invoice ID after save to prevent breaking the link
        if (!frm.is_new()) {
            frm.set_df_property("invoice_id", "read_only", 1);
        } else {
            frm.set_df_property("invoice_id", "read_only", 0);
        }

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
    validate(frm) {
        // Validate Price > 0
        (frm.doc.table_qecz || []).forEach(item => {
            if (flt(item.price) <= 0) {
                frappe.msgprint({
                    title: __("Invalid Price"),
                    message: __("Price cannot be 0 or less for item {0} in row {1}").format(
                        "<b>" + (item.service || "Unknown") + "</b>", 
                        "<b>" + item.idx + "</b>"
                    ),
                    indicator: "red"
                });
                frappe.validated = false;
            }
        });
    },
    table_qecz_remove(frm) {
        setTimeout(() => {
            if (window.purchase_calculate_totals_live) {
                window.purchase_calculate_totals_live(frm);
            }
        }, 200);
    },
    default_tax_type(frm) {
        if (!frm.doc.default_tax_type) return;

        // Get the selected tax type details (percentage is needed for instant recalculation)
        frappe.db.get_value("Tax Types", frm.doc.default_tax_type, ["name", "tax_percentage"], (r) => {
            if (r) {
                const tax_percent = flt(r.tax_percentage || 0);

                // Propagation Logic: ONLY auto-fill all items IF the type is 'Exempted'
                // For all other GST rates, items remain independent to allow mixed rates.
                if (r.name === "Exempted") {
                    frm.doc.table_qecz.forEach((item) => {
                        frappe.model.set_value(item.doctype, item.name, "tax_type", r.name);
                        frappe.model.set_value(item.doctype, item.name, "tax_percent", tax_percent);

                        if (window.purchase_calculate_row_amount) {
                            window.purchase_calculate_row_amount(item);
                        }
                    });
                }

                frm.refresh_field("table_qecz");
                if (window.purchase_calculate_totals_live) {
                    window.purchase_calculate_totals_live(frm);
                }
            }
        });
    },

    invoice_id(frm) {
        if (!frm.doc.invoice_id) return;

        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Invoice",
                name: frm.doc.invoice_id
            },
            callback: function (r) {
                if (r.message) {
                    let invoice = r.message;

                    // Set tax type
                    frm.set_value("default_tax_type", invoice.default_tax_type);

                    // Clear existing items
                    frm.clear_table("table_qecz");

                    // Fetch invoice items
                    if (invoice.table_qecz && invoice.table_qecz.length > 0) {
                        invoice.table_qecz.forEach(function (item) {
                            let purchase_item = frm.add_child("table_qecz");
                            purchase_item.service = item.service;
                            purchase_item.hsn_code = item.hsn_code;
                            purchase_item.description = item.description;
                            purchase_item.brand = item.brand;
                            purchase_item.quantity = item.quantity;
                            purchase_item.price = item.price;
                            purchase_item.discount_type = item.discount_type;
                            purchase_item.discount = item.discount;
                            purchase_item.tax_type = item.tax_type;
                            purchase_item.tax_percent = item.tax_percent;

                            // Fetch tax type details to get tax_type_master for proper calculation
                            if (item.tax_type) {
                                frappe.db.get_value("Tax Types", item.tax_type, ["tax_percentage", "tax_type"])
                                    .then(tax_r => {
                                        if (tax_r.message) {
                                            purchase_item.tax_percentage = Number(tax_r.message.tax_percentage || 0);
                                            purchase_item.tax_type_master = tax_r.message.tax_type;
                                        }
                                    });
                            }
                        });

                        frm.refresh_field("table_qecz");

                        // Trigger calculations after a short delay to ensure tax data is fetched
                        setTimeout(() => {
                            // Calculate each row
                            (frm.doc.table_qecz || []).forEach(row => {
                                if (window.purchase_calculate_row_amount) {
                                    window.purchase_calculate_row_amount(row);
                                }
                            });

                            // Calculate totals
                            if (window.purchase_calculate_totals_live) {
                                window.purchase_calculate_totals_live(frm);
                            }

                            frm.refresh_field("table_qecz");
                        }, 500);
                    }

                    frappe.show_alert({
                        message: __("Invoice details fetched successfully"),
                        indicator: "green"
                    }, 3);
                }
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
            // Set default_tax_type based on row selection (SILENT sync to avoid cascading overwrites)
            frm.set_value("default_tax_type", item.tax_type, null, true);
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