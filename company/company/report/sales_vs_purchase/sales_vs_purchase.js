// Copyright (c) 2025, deepak and contributors
// For license information, please see license.txt

frappe.query_reports["Sales vs purchase"] = {
    auto_run: true,

    filters: [
        {
            fieldname: "page",
            label: __("Page No"),
            fieldtype: "Int",
            default: 1,
            hidden: 1
        },
        {
            fieldname: "page_length",
            label: __("Page Size"),
            fieldtype: "Select",
            options: [
                { label: "10", value: 10 },
                { label: "20", value: 20 },
                { label: "50", value: 50 },
                { label: "100", value: 100 },
                { label: "500", value: 500 },
                { label: "All", value: 999999 }
            ],
            default: "10",
            hidden: 1
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -12)
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer",
            get_query: () => {
                return {
                    filters: {
                        customer_type: "Sales"
                    }
                };
            }
        },
        {
            fieldname: "vendor",
            label: __("Vendor"),
            fieldtype: "Link",
            options: "Customer",
            get_query: () => {
                return {
                    filters: {
                        customer_type: "Purchase"
                    }
                };
            }
        },
        {
            fieldname: "only_linked",
            label: __("Only Linked"),
            fieldtype: "Check",
            default: 1,
            hidden: 1
        },
        {
            fieldname: "sales_business_person",
            label: __("Sales Business Person"),
            fieldtype: "Link",
            options: "Business Person"
        },
        {
            fieldname: "purchase_business_person",
            label: __("Purchase Business Person"),
            fieldtype: "Link",
            options: "Business Person"
        }
    ],

    onload(report) {
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

        // Ensure "All" data is exported even when view is paginated and filters are hidden
        report.export_report = () => {
            const dialog = frappe.report_utils.get_export_dialog(
                __(report.report_name),
                [],
                ({ file_format }) => {
                    const filters = report.get_filter_values(true);
                    // Force full data for export
                    filters.page_length = 999999;
                    filters.page = 1;
                    filters.is_export = 1;

                    const args = {
                        cmd: "frappe.desk.query_report.export_query",
                        report_name: report.report_name,
                        file_format_type: file_format,
                        filters: filters,
                        visible_idx: [], // Clear this to ensure server sends everything
                        is_export: 1,    // Signal to backend
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
        const page = report.get_filter_value("page");
        const page_length = report.get_filter_value("page_length");

        setTimeout(() => {
            const datatable = report.datatable;
            if (!datatable || !datatable.datamanager) return;

            const rows = datatable.datamanager.getRows();

            if (report._prev_btn) {
                report._prev_btn.prop("disabled", page <= 1);
            }

            const is_last_page = rows.length < page_length;
            if (report._next_btn) {
                report._next_btn.prop("disabled", is_last_page);
            }

            // Safety: if user is on a high page after filtering and sees no data
            if (rows.length === 0 && page > 1) {
                report.set_filter_value("page", 1);
                report.refresh();
            }
        }, 0);
    },

    filters_config: [
        {
            "setup": function (report) {
                report.page.fields_dict.from_date.$input.on("change", () => report.set_filter_value("page", 1));
                report.page.fields_dict.to_date.$input.on("change", () => report.set_filter_value("page", 1));
                report.page.fields_dict.customer.$input.on("change", () => report.set_filter_value("page", 1));
                report.page.fields_dict.vendor.$input.on("change", () => report.set_filter_value("page", 1));
                report.page.fields_dict.sales_business_person.$input.on("change", () => report.set_filter_value("page", 1));
                report.page.fields_dict.purchase_business_person.$input.on("change", () => report.set_filter_value("page", 1));
            }
        }
    ]
};
