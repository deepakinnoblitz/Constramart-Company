frappe.query_reports["Sales Analytics"] = {
    auto_run: true,

    filters: [
        { fieldname: "page", fieldtype: "Int", default: 1, hidden: 1 },
        { fieldname: "page_length", fieldtype: "Int", default: 10, hidden: 1 },

        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -12)
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "invoice",
            label: __("Invoice"),
            fieldtype: "Link",
            options: "Invoice"
        },
        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "MultiSelectList",
            get_data: function (txt) {
                return frappe.db.get_link_options("Customer", txt);
            }
        },
        // {
        //     fieldname: "billing_name",
        //     label: __("Company Name"),
        //     fieldtype: "Data"
        // },
        {
            fieldname: "gst_non_gst",
            label: __("GST / Non-GST"),
            fieldtype: "Select",
            options: "\nGST\nNon-GST"
        },
        {
            fieldname: "business_person_name",
            label: __("Business Person"),
            fieldtype: "Link",
            options: "Business Person"
        },
        {
            fieldname: "location",
            label: __("Location"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.utils.filter_dict(frappe.query_report._location_options || [], { label: ["like", "%" + txt + "%"] });
            }
        },
    ],

    onload(report) {
        console.log("🛠️ Sales Analytics onload fired");
        report.set_filter_value("page_length", 10);

        report.page.add_inner_button(__("Export Invoice Details"), function () {
            let filters = report.get_filter_values(true) || {};

            frappe.call({
                method: 'company.company.api.get_sales_export_count',
                args: {
                    filters: JSON.stringify(filters)
                },
                callback: function (r) {
                    let counts = r.message || { invoice_count: 0, item_count: 0 };
                    let inv_count = counts.invoice_count || 0;

                    if (inv_count === 0) {
                        frappe.msgprint({
                            title: __('No Invoices Found'),
                            message: __('There are no invoices matching the selected filters to export.'),
                            indicator: 'orange'
                        });
                        return;
                    }

                    frappe.confirm(
                        __('Are you sure you want to download <b>{0} Invoice(s)</b> to Excel?', [inv_count]),
                        function () {
                            frappe.dom.freeze(__('Generating Excel Report, please wait...'));

                            fetch('/api/method/company.company.api.export_sales_itemized_excel', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/x-www-form-urlencoded',
                                    'X-Frappe-CSRF-Token': frappe.csrf_token
                                },
                                body: $.param({
                                    filters: JSON.stringify(filters)
                                })
                            })
                            .then(response => response.blob())
                            .then(blob => {
                                frappe.dom.unfreeze();
                                let url = window.URL.createObjectURL(blob);
                                let a = document.createElement('a');
                                a.href = url;
                                a.download = 'Sales_Item_Details_Report.xlsx';
                                document.body.appendChild(a);
                                a.click();
                                a.remove();
                                window.URL.revokeObjectURL(url);
                                frappe.show_alert({ message: __('Excel Report downloaded successfully!'), indicator: 'green' });
                            })
                            .catch(err => {
                                frappe.dom.unfreeze();
                                frappe.msgprint(__('Failed to generate Excel report. Please try again.'));
                            });
                        }
                    );
                }
            });
        });

        report._prev_btn = report.page.add_inner_button("⬅ Prev", () => {
            const page = report.get_filter_value("page");
            if (page > 1) {
                report.set_filter_value("page", page - 1);
                report.refresh();
            }
        });

        report._next_btn = report.page.add_inner_button("Next ➡", () => {
            const page = report.get_filter_value("page");
            report.set_filter_value("page", page + 1);
            report.refresh();
        });

        // Validation hint
        report.page.fields_dict.location.$input.on("focus", () => {
            const customer = report.get_filter_value("customer");
            if (!customer || (Array.isArray(customer) && customer.length === 0)) {
                frappe.msgprint(__("Please Select the Customer"));
            }
        });
    },

    after_refresh(report) {
        console.log("🔥 after_refresh fired");

        // 🚀 SYNC LOCATIONS IN after_refresh (FOOLPROOF METHOD)
        const value = report.get_filter_value("customer");
        let customers = Array.isArray(value) ? value : (value ? [value] : []);

        // Compare with last fetched to avoid infinite loops
        const current_customers_json = JSON.stringify(customers.sort());
        if (report._last_customers_json !== current_customers_json) {
            console.log("🔄 Customer selection changed, syncing locations...");
            report._last_customers_json = current_customers_json;

            if (customers.length > 0 && customers[0] !== "") {
                frappe.call({
                    method: "company.company.doctype.invoice.invoice.get_customer_locations",
                    args: {
                        customer: customers
                    },
                    callback: function (r) {
                        console.log("📍 Locations sync result:", r.message);
                        if (r.message && r.message.length > 0) {
                            options = r.message.map(row => ({ value: row.location_name, label: row.location_name, description: "" }));
                            frappe.show_alert({ message: __("Available locations updated"), indicator: 'green' });
                        } else {
                            options = [{ value: "none", label: "No Location Found" }];
                        }

                        report._location_options = options;
                        
                        // Clear current location selections if they are no longer valid (optional)
                        // report.set_filter_value("location", []);
                    }
                });
            } else {
                if (report.set_filter_property) {
                    report.set_filter_property("location", "options", [""]);
                } else {
                    report.page.fields_dict.location.df.options = [""];
                    report.page.fields_dict.location.refresh();
                }
            }
        }

        const page = report.get_filter_value("page");
        const page_length = report.get_filter_value("page_length");

        setTimeout(() => {
            const datatable = report.datatable;
            if (!datatable || !datatable.datamanager) return;
            const rows = datatable.datamanager.getRows();
            if (report._prev_btn) report._prev_btn.prop("disabled", page <= 1);
            if (report._next_btn) report._next_btn.prop("disabled", rows.length < page_length);
        }, 0);
    },

    "customer": function (report) {
        report.set_filter_value("page", 1);
    },

    "location": function (report) {
        report.set_filter_value("page", 1);
    },

    "invoice": function (report) {
        report.set_filter_value("page", 1);
    },

    filters_config: [
        {
            "setup": function (report) {
                const fields = ["from_date", "to_date", "invoice", "billing_name", "gst_non_gst", "business_person_name", "location"];
                fields.forEach(f => {
                    if (report.page.fields_dict[f]) {
                        report.page.fields_dict[f].$input.on("change", () => report.set_filter_value("page", 1));
                    }
                });
            }
        }
    ]
};
