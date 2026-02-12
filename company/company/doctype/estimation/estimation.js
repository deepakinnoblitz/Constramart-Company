frappe.ui.form.on("Estimation",
    {
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
            $('.page-icon-group .icon-btn').hide();

            // Show button only when document is saved
            if (!frm.doc.__islocal) {

                if (frm.doc.status !== "Customer Rejected" && frm.doc.status !== "Converted") {

                    frm.add_custom_button("Create Invoice", function () {

                        frappe.confirm(
                            __("Are you sure you want to convert this Estimation into an Invoice?"),
                            function () {
                                // 👉 YES clicked
                                frappe.call({
                                    method: "company.company.api.convert_estimation_to_invoice",
                                    args: {
                                        estimation: frm.doc.name
                                    },
                                    callback: function (r) {
                                        if (r.message) {
                                            frappe.set_route("Form", "Invoice", r.message);
                                        }
                                    }
                                });
                            },
                            function () {
                                // 👉 NO clicked — do nothing
                                frappe.show_alert({
                                    message: __("Operation cancelled"),
                                    indicator: "orange"
                                }, 3);
                            }
                        );

                    });

                }

                frm.add_custom_button("Preview PDF", function () {

                    let doctype = "Estimation";
                    let name = encodeURIComponent(frm.doc.name);
                    let format = encodeURIComponent("Estimation Print Style");

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

                }, "Print Estimation"); // Under Print dropdown



                frm.add_custom_button("Download PDF", function () {

                    let doctype = "Estimation";
                    let name = encodeURIComponent(frm.doc.name);
                    let format = encodeURIComponent("Estimation Print Style");

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

                }, "Print Estimation");


            }

        },

        validate(frm) {
            if (!frm.doc.table_qecz || frm.doc.table_qecz.length === 0) {
                frappe.msgprint(__("At least one item is required in the Items table."));
                frappe.validated = false;
            }
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

// Estimation Items child table logic
frappe.ui.form.on("Estimation Items", {
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