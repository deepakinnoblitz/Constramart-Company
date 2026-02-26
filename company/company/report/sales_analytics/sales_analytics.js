console.log("🔥 Sales Analytics JS LOADED");

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
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer"
        },
        {
            fieldname: "billing_name",
            label: __("Company Name"),
            fieldtype: "Data"
        },
        {
            fieldname: "gst_non_gst",
            label: __("GST / Non-GST"),
            fieldtype: "Select",
            options: "\nGST\nNon-GST"
        }
    ],

    // ----------------------------
    // SETUP (RUNS ONCE)
    // ----------------------------
    onload(report) {
        console.log("✅ onload fired");

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
        console.log("🔥 after_refresh fired");

        const page = report.get_filter_value("page");
        const page_length = report.get_filter_value("page_length");

        setTimeout(() => {
            const datatable = report.datatable;
            if (!datatable || !datatable.datamanager) return;

            const rows = datatable.datamanager.getRows();
            console.log("Rows:", rows.length, "Page:", page);

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
