
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
            fieldtype: "Select",
            options: [""]
        },
    ],

    onload(report) {
        console.log("🛠️ Sales Analytics onload fired");
        report.set_filter_value("page_length", 10);

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
                        let options = [""];
                        if (r.message && r.message.length > 0) {
                            options = options.concat(r.message.map(row => row.location_name));
                            frappe.show_alert({ message: __("Available locations updated"), indicator: 'green' });
                        } else {
                            options = ["No Location Found"];
                        }

                        if (report.set_filter_property) {
                            report.set_filter_property("location", "options", options);
                        } else {
                            report.page.fields_dict.location.df.options = options;
                            report.page.fields_dict.location.refresh();
                        }
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
