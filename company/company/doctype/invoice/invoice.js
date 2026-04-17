// Copyright (c) 2025, deepak and contributors
// For license information, please see license.txt

frappe.ui.form.on("Invoice", {
    onload(frm) {
        if (!frm.doc.bank_account) {
            frm.set_value("bank_account", "BACC00001");
        }

        if (frm.is_new() && (!frm.doc.table_qecz || frm.doc.table_qecz.length === 0)) {
            frm.add_child("table_qecz");
            frm.refresh_field("table_qecz");
        }
    },
    refresh(frm) {
        toggle_conversion_section(frm);
        set_tax_filters(frm);
        setup_location_trigger(frm);

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
                        let item = locals["Invoice Items"][docname];
                        let fieldname = $(this).attr("data-fieldname");
                        // If model still has value, clear it immediately
                        if (item && item[fieldname]) {
                            frappe.model.set_value(item.doctype, item.name, fieldname, "");
                        }
                    }
                }
            }
        );

        if (!frm.is_new()) {
            frm.set_df_property("purchase_id", "read_only", 1);
        } else {
            frm.set_df_property("purchase_id", "read_only", 0);
            
            // Filter Purchase ID to only show unlinked Purchases
            frm.set_query("purchase_id", function () {
                return {
                    query: "company.company.api.get_unlinked_purchases"
                };
            });
        }

        // Lock form if collections exist
        if (!frm.is_new()) {
            frappe.db.count("Invoice Collection", { filters: { invoice: frm.doc.name } }).then(count => {
                if (count > 0) {
                    frm.set_read_only();
                    frm.disable_save();
                    frm.set_intro(
                        __("This Invoice is {0} because {1} Payment Collection(s) have been recorded. To edit this Invoice, please delete the linked collections first.",
                            ["<b class='text-danger'>Locked</b>", "<b>" + count + "</b>"]),
                        "red"
                    );

                    // Hide "Not Saved" indicator to avoid confusion
                    $(".indicator-pill:contains('Not Saved')").hide();
                }
            });
        }

        if (!frm.doc.__islocal) {

            frm.add_custom_button("Preview PDF", function () {

                let doctype = "Invoice";
                let name = encodeURIComponent(frm.doc.name);
                let format = encodeURIComponent("Invoice Print Format");

                // Preview PDF (open in browser)
                let url = `/api/method/frappe.utils.print_format.download_pdf?
                doctype=${doctype}
                &name=${name}
                &format=${format}
                &no_letterhead=1
                &letterhead=No Letterhead
                &settings={}
                &trigger_print=0
            `.replace(/\s+/g, "");

                window.open(url, "_blank");

            }, "Print Invoice"); // Under Print dropdown



            frm.add_custom_button("Download PDF", function () {

                let doctype = "Invoice";
                let name = encodeURIComponent(frm.doc.name);
                let format = encodeURIComponent("Invoice Print Format");

                // ⬇️ Force Download URL
                let url = `/api/method/frappe.utils.print_format.download_pdf?
                doctype=${doctype}
                &name=${name}
                &format=${format}
                &no_letterhead=1
                &letterhead=No Letterhead
                &settings={}
                &download=1
            `.replace(/\s+/g, "");

                // === FORCE DOWNLOAD ===
                let a = document.createElement("a");
                a.href = url;
                a.download = `${frm.doc.name}.pdf`;
                document.body.appendChild(a);
                a.click();
                a.remove();

            }, "Print Invoice");


            // Collection Management Buttons
            if (flt(frm.doc.balance_amount, 2) > 0) {
                frm.add_custom_button(__("Create Collection"), function () {
                    frappe.new_doc("Invoice Collection", {
                        invoice: frm.doc.name,
                        customer_id: frm.doc.customer_id,
                        customer_name: frm.doc.customer_name,
                        company_name: frm.doc.billing_name,
                        amount_to_pay: frm.doc.balance_amount,
                        collection_date: frappe.datetime.get_today()
                    });
                }, __("Collections"));
            }

            frm.add_custom_button(__("View Collections"), function () {
                frappe.set_route("List", "Invoice Collection", {
                    "invoice": frm.doc.name
                });
            }, __("Collections"));

        }
    },
    table_qecz_remove(frm) {
        // Delay to ensure the row is removed from frm.doc.table_qecz before calculation
        setTimeout(() => {
            if (window.calculate_totals_live) {
                window.calculate_totals_live(frm);
            }

            // If table is empty, clear default_tax_type
            if (!frm.doc.table_qecz || frm.doc.table_qecz.length === 0) {
                frm.set_value("default_tax_type", "");
                frm.refresh_field("default_tax_type");
                set_tax_filters(frm);
            }
        }, 200);
    },
    converted_from_estimation(frm) {
        toggle_conversion_section(frm);
    },
    client_name(frm) {
        if (!frm.doc.client_name) return;

        frappe.db.get_value("Customer", frm.doc.client_name,
            ["phone_number"],
            (r) => {
                if (r) {
                    frm.set_value("phone_number", r.phone_number || "");
                }
            });
    },

    // Tax auto-fill logic
    default_tax_type(frm) {
        if (!frm.doc.default_tax_type) {
            set_tax_filters(frm);
            return;
        }

        // Get the selected tax type details (percentage is needed for instant recalculation)
        frappe.db.get_value("Tax Types", frm.doc.default_tax_type, ["name", "tax_percentage", "tax_type"], (r) => {
            if (r) {
                const tax_percent = flt(r.tax_percentage || 0);
                const tax_type_master = r.tax_type;

                // Auto-fill all items and RECALCULATE immediately
                (frm.doc.table_qecz || []).forEach((item) => {
                    frappe.model.set_value(item.doctype, item.name, "tax_type", r.name);
                    
                    // Unified field update (DocType field is 'tax_percent', Script expects 'tax_percentage')
                    frappe.model.set_value(item.doctype, item.name, "tax_percent", tax_percent);
                    item.tax_percentage = tax_percent;
                    item.tax_type_master = tax_type_master;
                    
                    if (window.calculate_row_amount_dynamic) {
                        window.calculate_row_amount_dynamic(item);
                    }
                });
                
                frm.refresh_field("table_qecz");
                if (window.calculate_totals_live) {
                    window.calculate_totals_live(frm);
                }
            }
        });
        set_tax_filters(frm);
    },

    validate(frm) {
        if (!frm.doc.table_qecz || frm.doc.table_qecz.length === 0) {
            frappe.msgprint(__("At least one item is required in the Items table."));
            frappe.validated = false;
        }
    },

    purchase_id(frm) {
        if (!frm.doc.purchase_id) return;

        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Purchase",
                name: frm.doc.purchase_id
            },
            callback: function (r) {
                if (r.message) {
                    let purchase = r.message;

                    // Set tax type
                    frm.set_value("default_tax_type", purchase.default_tax_type);

                    // Clear existing items
                    frm.clear_table("table_qecz");

                    // Fetch purchase items
                    if (purchase.table_qecz && purchase.table_qecz.length > 0) {
                        purchase.table_qecz.forEach(function (item) {
                            let invoice_item = frm.add_child("table_qecz");
                            invoice_item.service = item.service;
                            invoice_item.hsn_code = item.hsn_code;
                            invoice_item.description = item.description;
                            invoice_item.brand = item.brand;
                            invoice_item.quantity = item.quantity;
                            invoice_item.price = item.price;
                            invoice_item.discount_type = item.discount_type;
                            invoice_item.discount = item.discount;
                            invoice_item.tax_type = item.tax_type;
                            invoice_item.tax_percent = item.tax_percent;

                            // Fetch tax type details to get tax_type_master for proper calculation
                            if (item.tax_type) {
                                frappe.db.get_value("Tax Types", item.tax_type, ["tax_percentage", "tax_type"])
                                    .then(tax_r => {
                                        if (tax_r.message) {
                                            invoice_item.tax_percentage = Number(tax_r.message.tax_percentage || 0);
                                            invoice_item.tax_type_master = tax_r.message.tax_type;
                                        }
                                    });
                            }
                        });

                        frm.refresh_field("table_qecz");

                        // Trigger calculations after a short delay to ensure tax data is fetched
                        setTimeout(() => {
                            // Calculate each row
                            (frm.doc.table_qecz || []).forEach(row => {
                                if (window.calculate_row_amount_dynamic) {
                                    window.calculate_row_amount_dynamic(row);
                                }
                            });

                            // Calculate totals
                            if (window.calculate_totals_live) {
                                window.calculate_totals_live(frm);
                            }

                            frm.refresh_field("table_qecz");
                        }, 500);
                    }

                    frappe.show_alert({
                        message: __("Purchase details fetched successfully"),
                        indicator: "green"
                    }, 3);
                }
            }
        });
    }
});

// Invoice Items child table logic
frappe.ui.form.on("Invoice Items", {
    before_table_qecz_add(frm, cdt, cdn) {
        // Apply default tax when adding new row
        if (frm.doc.default_tax_type) {
            // Will be set after row is added
            setTimeout(() => {
                let items = frm.doc.table_qecz;
                if (items && items.length > 0) {
                    let last_item = items[items.length - 1];
                    frappe.model.set_value(last_item.doctype, last_item.name, "tax_type", frm.doc.default_tax_type);
                }
            }, 100);
        }
    },

    tax_type(frm, cdt, cdn) {
        let item = locals[cdt][cdn];
        if (item.tax_type) {
            // Set default_tax_type based on row selection
            frm.set_value("default_tax_type", item.tax_type);
        } else {
            // If tax_type is cleared, check if ANY other row has a tax_type
            let other_tax = (frm.doc.table_qecz || []).find(d => d.tax_type);
            if (!other_tax) {
                frm.set_value("default_tax_type", "");
            }
        }
        frm.refresh_field("default_tax_type");
        set_tax_filters(frm);
    }
});

function set_tax_filters(frm) {
    const is_exempted = frm.doc.default_tax_type === "Exempted";

    // Hide "Create New" if Exempted
    frm.fields_dict.table_qecz.grid.update_docfield_property("tax_type", "only_select", is_exempted ? 1 : 0);

    // Use set_query with dynamic doc evaluation to beat caching
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
}

function toggle_conversion_section(frm) {
    if (frm.doc.converted_from_estimation == 1) {
        // Show the section
        frm.set_df_property("converted_from_estimation", "hidden", 0);
        frm.set_df_property("converted_estimation_id", "hidden", 0);
    } else {
        // Hide the section
        frm.set_df_property("converted_from_estimation", "hidden", 1);
        frm.set_df_property("converted_estimation_id", "hidden", 1);
    }
}

function setup_location_trigger(frm) {
    // Add a placeholder to the location field
    frm.set_df_property("location", "placeholder", __("Click to select or create location"));

    // Ensure only ONE listener is attached (off() removes any previous listeners)
    $(frm.fields_dict.location.input).off("click").on("click", function () {
        show_location_dialog(frm);
    });
}

function show_location_dialog(frm) {
    if (!frm.doc.customer_id) {
        frappe.msgprint(__("Please select a Customer first."));
        return;
    }

    // Fetch existing locations from Customer
    frappe.db.get_doc("Customer", frm.doc.customer_id).then(customer => {
        let locations = (customer.location || []).map(row => row.location_name);
        let location_options = locations.length > 0 ? ["", ...locations] : ["No Location Available"];

        let d = new frappe.ui.Dialog({
            title: __("Select or Create Location"),
            fields: [
                {
                    label: __("Select Existing Location"),
                    fieldname: "existing_location",
                    fieldtype: "Select",
                    options: location_options
                },
                {
                    label: __("Location Name"),
                    fieldname: "location_name",
                    fieldtype: "Data",
                    reqd: 1
                },
                {
                    label: __("Address"),
                    fieldname: "address",
                    fieldtype: "Small Text"
                }
            ],
            primary_action_label: __("Apply to Invoice"),
            primary_action(values) {
                // Update Invoice fields (deferred save to Customer until Invoice save)
                frm.set_value("location", values.location_name);
                frm.set_value("location_address", values.address);
                frm.set_value("is_new_location", 1);

                d.hide();
            }
        });

        // 📝 PRE-FILL DATA FROM FORM
        if (frm.doc.location) {
            if (locations.includes(frm.doc.location)) {
                d.set_value("existing_location", frm.doc.location);
                d.set_value("location_name", frm.doc.location);
                
                // Trigger logic to set address and hide fields
                let row = customer.location.find(r => r.location_name === frm.doc.location);
                if (row) d.set_value("address", row.address || "");
                
                d.get_field("location_name").df.reqd = 0;
                d.get_field("location_name").df.hidden = 1;
                d.get_field("address").df.hidden = 1;
                setTimeout(() => {
                    if (d.fields_dict.location_name) d.fields_dict.location_name.$wrapper.hide();
                    if (d.fields_dict.address) d.fields_dict.address.$wrapper.hide();
                }, 100);
            } else {
                d.set_value("location_name", frm.doc.location);
                d.set_value("address", frm.doc.location_address || "");
            }
        }

        // 🚀 Robust Event Listener for visibility toggle
        d.fields_dict.existing_location.$input.on("change", function () {
            let selected = d.get_value("existing_location");
            if (selected && selected !== "No Location Available") {
                d.set_value("location_name", selected);
                // Find address
                let row = (customer.location || []).find(r => r.location_name === selected);
                if (row) {
                    d.set_value("address", row.address || "");
                }
                // Force Hide and make NOT required (since it's filled automatically)
                d.get_field("location_name").df.reqd = 0;
                d.get_field("location_name").df.hidden = 1;
                d.get_field("address").df.hidden = 1;
                d.fields_dict.location_name.$wrapper.hide();
                d.fields_dict.address.$wrapper.hide();
            } else {
                // Force Show and make required for new entry
                d.set_value("location_name", "");
                d.set_value("address", "");
                d.get_field("location_name").df.reqd = 1;
                d.get_field("location_name").df.hidden = 0;
                d.get_field("address").df.hidden = 0;
                d.fields_dict.location_name.$wrapper.show();
                d.fields_dict.address.$wrapper.show();
            }
        });

        d.show();
    });
}