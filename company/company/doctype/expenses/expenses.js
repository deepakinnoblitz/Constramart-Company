frappe.ui.form.on("Expenses", {
    onload(frm) {
        // Add a default row if it's a new record and table is empty
        if (frm.is_new() && (!frm.doc.table_qecz || frm.doc.table_qecz.length === 0)) {
            frm.add_child("table_qecz");
            frm.refresh_field("table_qecz");
        }
    },

    validate(frm) {
        // Ensure at least one row exists
        if (!frm.doc.table_qecz || frm.doc.table_qecz.length === 0) {
            frappe.msgprint({
                title: __("Mandatory Table"),
                message: __("At least one Expense Item is required."),
                indicator: "red"
            });
            frappe.validated = false;
        }

        // Validate Price > 0
        let invalid_items = (frm.doc.table_qecz || []).filter(item => flt(item.price) <= 0);
        if (invalid_items.length > 0) {
            frappe.validated = false;

            let item_ids = invalid_items.map(i => i.service || i.items).filter(Boolean);
            let item_map = {};
            if (item_ids.length > 0) {
                frappe.call({
                    method: "company.company.api.get_item_names",
                    args: { item_ids: item_ids },
                    async: false,
                    callback: function (r) {
                        item_map = r.message || {};
                    }
                });
            }

            invalid_items.forEach(item => {
                let code = item.service || item.items || "Unknown";
                let name = item_map[code];
                let display_name = name ? `${name} (${code})` : code;

                frappe.msgprint({
                    title: __("Invalid Price"),
                    message: __("Price cannot be 0 or less for item {0} in row {1}", [
                        "<b>" + display_name + "</b>",
                        "<b>" + item.idx + "</b>"
                    ]),
                    indicator: "red"
                });
            });
        }
    }
});
