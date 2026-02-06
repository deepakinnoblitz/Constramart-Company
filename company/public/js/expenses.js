// =================== EXPENSES FORM SCRIPT ===================
frappe.ui.form.on("Expenses", {
    onload_post_render: function(frm) {
        // Set today's date by default
        if (!frm.doc.date) {
            frm.set_value("date", frappe.datetime.get_today());
        }

        // Live calculation for child table totals when inputs change
        const table_wrapper = frm.fields_dict.table_qecz?.grid.wrapper;
        if (table_wrapper) {
            table_wrapper.on(
                'input',
                'input[data-fieldname="quantity"], input[data-fieldname="price"]',
                function() {
                    calculate_totals(frm);
                }
            );
        }

        calculate_totals(frm);
    },

    table_qecz_add: function(frm) {
        calculate_totals(frm);
    },

    table_qecz_remove: function(frm) {
        calculate_totals(frm);
    }
});

// =================== CHILD TABLE SCRIPT ===================
frappe.ui.form.on("Expenses Items", {
    quantity: function(frm, cdt, cdn) {
        update_row(frm, cdt, cdn);
    },
    price: function(frm, cdt, cdn) {
        update_row(frm, cdt, cdn);
    }
});

// =================== HELPER FUNCTIONS ===================
function update_row(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row) return;

    // Calculate amount for the row
    row.amount = flt((row.quantity || 0) * (row.price || 0), 2);

    // Refresh the child table row
    frm.refresh_field("table_qecz");

    // Recalculate total in parent form
    calculate_totals(frm);
}

function calculate_totals(frm) {
    let total = 0.0;

    (frm.doc.table_qecz || []).forEach(row => {
        if (row.amount) total += flt(row.amount, 2);
    });

    frm.set_value("total", total);
    frm.refresh_field("total");
}

frappe.ui.form.on('Expenses', {
    onload: function(frm) {
        if (!frm.doc.expense_no) {
            frappe.call({
                method: "company.company.api.get_next_expense_preview",
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('expense_no', r.message);
                    }
                }
            });
        }
    }
});

