// Copyright (c) 2025, deepak and contributors
// For license information, please see license.txt

frappe.query_reports["Purchase Report"] = {
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
            fieldname: "purchase_id",
            label: __("Purchase ID"),
            fieldtype: "Link",
            options: "Purchase"
        },
        {
            fieldname: "vendor_id",
            label: __("Vendor ID"),
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
            fieldname: "vendor_name",
            label: __("Vendor Name"),
            fieldtype: "Data"
        },
        {
            fieldname: "gst_non_gst",
            label: __("GST / Non-GST"),
            fieldtype: "Select",
            options: "\nGST\nNon-GST"
        },
        {
            fieldname: "purchase_status",
            label: __("Purchase Status"),
            fieldtype: "Select",
            options: "\nPending\nPartially Paid\nFully Paid"
        }
    ],

    // ----------------------------
    // SETUP (RUNS ONCE)
    // ----------------------------
    onload(report) {
        report.set_filter_value("page_length", 10);

        // Store button references
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

    // ----------------------------
    // DATA LOGIC
    // ----------------------------
    after_refresh(report) {
        const page = report.get_filter_value("page");
        const page_length = report.get_filter_value("page_length");

        setTimeout(() => {
            const datatable = report.datatable;
            if (!datatable || !datatable.datamanager) return;

            const rows = datatable.datamanager.getRows();

            // Disable Prev on first page
            if (report._prev_btn) {
                report._prev_btn.prop("disabled", page <= 1);
            }

            // Last page detection
            const is_last_page = rows.length < page_length;

            // Disable / enable Next
            if (report._next_btn) {
                report._next_btn.prop("disabled", is_last_page);
            }

            // Safety: if user goes beyond last page
            if (rows.length === 0 && page > 1) {
                report.set_filter_value("page", page - 1);
                report.refresh();
            }

        }, 0);
    }
};
