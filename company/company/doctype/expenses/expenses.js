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
        (frm.doc.table_qecz || []).forEach(item => {
            if (flt(item.price) <= 0) {
                frappe.msgprint({
                    title: __("Invalid Price"),
                    message: __("Price cannot be 0 or less for item {0} in row {1}").format(
                        "<b>" + (item.items || "Unknown") + "</b>", 
                        "<b>" + item.idx + "</b>"
                    ),
                    indicator: "red"
                });
                frappe.validated = false;
            }
        });
    }
});
