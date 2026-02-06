// Copyright (c) 2025, deepak and contributors
// For license information, please see license.txt

frappe.query_reports["Purchase Collection Report"] = {
    filters: [
        {
            fieldname: "purchase",
            label: "Purchase",
            fieldtype: "Link",
            options: "Purchase"
        },
        {
            fieldname: "vendor_id",
            label: "Vendor",
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
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date"
        },
        {
            fieldname: "only_pending",
            label: "Only Pending",
            fieldtype: "Check"
        },
        {
            fieldname: "show_last_collected",
            label: "Show Last Collected",
            fieldtype: "Check",
            default: 0
        }
    ]
};

frappe.query_reports["Purchase Collection Summary"] = {
    filters: [
        { fieldname: "purchase", label: "Purchase", fieldtype: "Link", options: "Purchase" },
        {
            fieldname: "vendor_id",
            label: "Vendor",
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
        { fieldname: "from_date", label: "From Date", fieldtype: "Date" },
        { fieldname: "to_date", label: "To Date", fieldtype: "Date" },
        { fieldname: "only_pending", label: "Only Pending", fieldtype: "Check" },
        {
            fieldname: "show_last_collected",
            label: "Show Last Collected",
            fieldtype: "Check",
            default: 1
        }
    ]
};
