frappe.ui.form.on("Item", {
    validate: async function (frm) {

        // 🔒 Only affect Quick Entry
        if (!frm.is_quick_entry) return;

        const is_duplicate = await check_item_duplicate_qe(frm);

        if (is_duplicate) {
            frappe.validated = false; // ⛔ block save
            return false;             // ⛔ stop QE flow
        }
    }
});


async function check_item_duplicate_qe(frm) {
    const item_name = frm.doc.item_name;
    const item_code = frm.doc.item_code;
    const docname = frm.doc.name || "";

    if (!item_name && !item_code) return false;

    // Item Name check
    if (item_name) {
        const r = await frappe.db.get_value(
            "Item",
            { item_name, name: ["!=", docname] },
            "name"
        );

        if (r?.message?.name) {
            frappe.msgprint({
                title: __("Duplicate Item"),
                message: __("Item Name already exists"),
                indicator: "red"
            });
            return true;
        }
    }

    // Item Code / HSN check
    if (item_code) {
        const r = await frappe.db.get_value(
            "Item",
            { item_code, name: ["!=", docname] },
            "name"
        );

        if (r?.message?.name) {
            frappe.msgprint({
                title: __("Duplicate Item"),
                message: __("Item Code / HSN already exists"),
                indicator: "red"
            });
            return true;
        }
    }

    return false;
}
