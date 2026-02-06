// Copyright (c) 2025, deepak and contributors
// For license information, please see license.txt

frappe.query_reports["Sales vs purchase"] = {
    auto_run: true,

    filters: [
        { fieldname: "page", fieldtype: "Int", default: 1, hidden: 1 },
        { fieldname: "page_length", fieldtype: "Int", default: 10, hidden: 1 },
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
            default: 1
        }
    ],

    onload(report) {
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
        }, 0);
    }
};
