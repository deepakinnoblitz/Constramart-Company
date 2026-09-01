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
        // {
        //     fieldname: "vendor_name",
        //     label: __("Vendor Name"),
        //     fieldtype: "Data"
        // },
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
        },
        {
            fieldname: "business_person_name",
            label: __("Business Person"),
            fieldtype: "Link",
            options: "Business Person"
        }
    ],

    // ----------------------------
    // SETUP (RUNS ONCE)
    // ----------------------------
    onload(report) {
        report.set_filter_value("page_length", 10);

        report.page.add_inner_button(__("Export Purchase Details"), function () {
            let filters = report.get_filter_values(true) || {};

            frappe.call({
                method: 'company.company.api.get_purchase_export_count',
                args: {
                    filters: JSON.stringify(filters)
                },
                callback: function (r) {
                    let counts = r.message || { purchase_count: 0, item_count: 0 };
                    let pur_count = counts.purchase_count || 0;

                    if (pur_count === 0) {
                        frappe.msgprint({
                            title: __('No Purchases Found'),
                            message: __('There are no purchases matching the selected filters to export.'),
                            indicator: 'orange'
                        });
                        return;
                    }

                    frappe.confirm(
                        __('Are you sure you want to download <b>{0} Purchase(s)</b> to Excel?', [pur_count]),
                        function () {
                            frappe.dom.freeze(__('Generating Excel Report, please wait...'));

                            fetch('/api/method/company.company.api.export_purchase_itemized_excel', {
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
                                a.download = 'Purchase_Item_Details_Report.xlsx';
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
