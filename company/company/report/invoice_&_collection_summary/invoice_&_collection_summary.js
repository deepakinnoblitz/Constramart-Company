
// Copyright (c) 2025, deepak and contributors
// For license information, please see license.txt

frappe.query_reports["Invoice & Collection Summary"] = {
    "filters": [
        { fieldname: "page", fieldtype: "Int", default: 1, hidden: 1 },
        { fieldname: "page_length", fieldtype: "Int", default: 10, hidden: 1 },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        },
        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "MultiSelectList",
            get_data: function (txt) {
                return frappe.db.get_link_options("Customer", txt);
            }
        },
        {
            fieldname: "invoice",
            label: __("Invoice"),
            fieldtype: "Link",
            options: "Invoice"
        },
        {
            fieldname: "business_person",
            label: __("Business Person"),
            fieldtype: "Link",
            options: "Business Person"
        },
        {
            fieldname: "show_only_last_collection",
            label: __("Show Only Last Collection"),
            fieldtype: "Check",
            default: 0
        },
        {
            fieldname: "location",
            label: __("Location"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.utils.filter_dict(frappe.query_report._location_options || [], { label: ["like", "%" + txt + "%"] });
            }
        }
    ],

    onload(report) {
        console.log("🛠️ Invoice & Collection Summary onload fired");
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

        report.page.fields_dict.location.$input.on("focus", () => {
            const customer = report.get_filter_value("customer");
            if (!customer) {
                frappe.msgprint(__("Please Select the Customer"));
            }
        });

        // Ensure "All" data is exported even when view is paginated and filters are hidden
        report.export_report = () => {
            const dialog = frappe.report_utils.get_export_dialog(
                __(report.report_name),
                [],
                ({ file_format }) => {
                    const filters = report.get_filter_values(true);
                    filters.page_length = 999999;
                    filters.page = 1;
                    filters.is_export = 1;
                    const args = {
                        cmd: "frappe.desk.query_report.export_query",
                        report_name: report.report_name,
                        file_format_type: file_format,
                        filters: filters,
                        visible_idx: [], 
                        is_export: 1,    
                        include_indentation: 0,
                        include_filters: 0,
                        export_in_background: 0
                    };
                    open_url_post(frappe.request.url, args);
                }
            );
            dialog.show();
        };
    },

    after_refresh(report) {
        console.log("🔥 after_refresh fired");

        // 🚀 SYNC LOCATIONS IN after_refresh (FOOLPROOF METHOD)
        const value = report.get_filter_value("customer");
        let customers = Array.isArray(value) ? value : (value ? [value] : []);

        const current_customers_json = JSON.stringify(customers.sort());
        if (report._last_customers_json !== current_customers_json) {
            console.log("🔄 Customer selections changed, syncing locations...");
            report._last_customers_json = current_customers_json;

            if (customers.length > 0 && customers[0] !== "") {
                frappe.call({
                    method: "company.company.doctype.invoice.invoice.get_customer_locations",
                    args: {
                        customer: customers
                    },
                    callback: function (r) {
                        console.log("📍 Locations sync result:", r.message);
                        let options = [];
                        if (r.message && r.message.length > 0) {
                            options = r.message.map(row => ({ value: row.location_name, label: row.location_name, description: "" }));
                            frappe.show_alert({ message: __("Available locations updated"), indicator: 'green' });
                        } else {
                            options = [{ value: "none", label: "No Location Found", description: "" }];
                        }

                        report._location_options = options;
                    }
                });
            } else {
                report._location_options = [];
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

    filters_config: [
        {
            "setup": function (report) {
                const fields = ["from_date", "to_date", "invoice", "business_person", "location"];
                fields.forEach(f => {
                    if(report.page.fields_dict[f]) {
                        report.page.fields_dict[f].$input.on("change", () => report.set_filter_value("page", 1));
                    }
                });
            }
        }
    ]
};
