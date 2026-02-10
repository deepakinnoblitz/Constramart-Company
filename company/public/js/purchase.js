// =================== PURCHASE FORM SCRIPT ===================
frappe.ui.form.on("Purchase", {
    onload_post_render: function (frm) {

        // Filter Vendor Name to only show Customers with customer_type = 'Purchase'
        frm.set_query("vendor_name", function () {
            return {
                filters: {
                    customer_type: "Purchase"
                }
            };
        });

        // Set today's bill date by default
        if (!frm.doc.bill_date) {
            frm.set_value("bill_date", frappe.datetime.get_today());
        }

        // Live discount listeners
        $(frm.fields_dict.overall_discount.input).on("input", () => calculate_totals_live(frm));
        $(frm.fields_dict.overall_discount_type.input).on("change", () => calculate_totals_live(frm));

        // Live calculation for child table quantity/price/discount
        frm.fields_dict.table_qecz.grid.wrapper.on(
            'input change',
            'input[data-fieldname="quantity"], input[data-fieldname="price"], input[data-fieldname="discount"], select[data-fieldname="discount_type"]',
            function () {
                const $row = $(this).closest("tr");
                const row_name = $row.attr("data-name");
                const row = locals["Purchase Items"][row_name];
                if (!row) return;

                row.quantity = parseFloat($row.find('input[data-fieldname="quantity"]').val() || 0);
                row.price = parseFloat($row.find('input[data-fieldname="price"]').val() || 0);
                row.discount = parseFloat($row.find('input[data-fieldname="discount"]').val() || 0);

                // Fetch available quantity if not already fetched
                if (row.service && row.available_qty === undefined) {
                    frappe.db.get_value("Item", row.service, ["available_qty"])
                        .then(r => {
                            if (r && r.message) {
                                row.available_qty = flt(r.message.available_qty || 0);
                                validate_and_calculate(row, frm);
                            }
                        });
                } else {
                    validate_and_calculate(row, frm);
                }
            }
        );
        // Batch delete listener (Toolbar button)
        frm.fields_dict.table_qecz.grid.wrapper.on("click", ".grid-remove-rows", function () {
            setTimeout(() => {
                calculate_totals_live(frm);
            }, 600);
        });

        calculate_totals_live(frm);
    },

    overall_discount: function (frm) { calculate_totals_live(frm); },
    overall_discount_type: function (frm) { calculate_totals_live(frm); },

    refresh(frm) {
        // Detect rounding mode from existing roundoff
        if (frm.doc.roundoff) {
            const natural = flt(frm.doc.grand_total - frm.doc.roundoff, 2);
            if (flt(frm.doc.grand_total, 0) === flt(frm.doc.grand_total, 2)) {
                if (frm.doc.grand_total === Math.floor(natural)) frm._rounding_mode = 'floor';
                else if (frm.doc.grand_total === Math.ceil(natural)) frm._rounding_mode = 'ceil';
            }
        }
    }
});

// =================== CHILD TABLE SCRIPT ===================
frappe.ui.form.on("Purchase Items", {
    service: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row || !row.service) return;

        frappe.db.get_value("Item", row.service, ["rate", "available_qty", "item_name", "item_code"])
            .then(r => {
                if (r && r.message) {
                    row.price = flt(r.message.rate || 0);
                    row.hsn_code = r.message.item_code || "";
                    row.available_qty = flt(r.message.available_qty || 0);
                    row.description = r.message.item_name || "";
                    row.sub_total = calculate_row_amount(row);
                    frm.refresh_field("table_qecz");
                    calculate_totals_live(frm);
                }
            });
    },

    quantity: function (frm, cdt, cdn) { child_update(frm, cdt, cdn); },
    price: function (frm, cdt, cdn) { child_update(frm, cdt, cdn); },
    discount: function (frm, cdt, cdn) { child_update(frm, cdt, cdn); },
    discount_type: function (frm, cdt, cdn) { child_update(frm, cdt, cdn); },
    tax_type: function (frm, cdt, cdn) { child_update(frm, cdt, cdn); }
});

// =================== HELPER FUNCTIONS ===================
function child_update(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row) return;
    validate_and_calculate(row, frm);
}

function validate_and_calculate(row, frm) {
    row.sub_total = calculate_row_amount(row);
    frm.refresh_field("table_qecz");
    calculate_totals_live(frm);
}

function calculate_row_amount(row) {
    let base_amount = (row.quantity || 0) * (row.price || 0);

    let discount_amt = 0;
    if (row.discount_type === "Percentage") discount_amt = base_amount * (row.discount || 0) / 100;
    else if (row.discount_type === "Flat") discount_amt = row.discount || 0;

    let taxable = base_amount - discount_amt;

    // Use the fetched tax_percent from Tax Types (not hardcoded)
    let tax_rate = parseFloat(row.tax_percent || 0);

    row.tax_amount = (taxable * tax_rate) / 100;
    return taxable + row.tax_amount;
}

// =================== GRAND TOTAL CALCULATION ===================
window.purchase_calculate_totals_live = function calculate_totals_live(frm) {
    let total_qty = 0.0;
    let total_amount = 0.0;

    (frm.doc.table_qecz || []).forEach(row => {
        total_qty += flt(row.quantity, 2);
        // Sum rounded subtotals to avoid floating point drift (Accounting Standard)
        total_amount += flt(row.sub_total, 2);
    });

    const discount_val = flt(frm.doc.overall_discount, 2);
    const discount_type_val = frm.doc.overall_discount_type || "Flat";

    let natural_total = total_amount;

    if (discount_type_val === "Flat") {
        natural_total = total_amount - discount_val;
    } else if (discount_type_val === "Percentage") {
        natural_total = total_amount - (total_amount * discount_val / 100);
    }

    // Prevent negative total
    natural_total = natural_total < 0 ? 0.0 : flt(natural_total, 2);

    frm.set_value("total_qty", flt(total_qty, 2));
    frm.set_value("total_amount", flt(total_amount, 2));

    // Always update grand_total by adding roundoff to the natural total
    let roundoff = flt(frm.doc.roundoff || 0, 2);

    // Apply persistent rounding mode if active
    if (frm._rounding_mode) {
        if (frm._rounding_mode === 'floor') roundoff = flt(Math.floor(natural_total) - natural_total, 2);
        else if (frm._rounding_mode === 'ceil') roundoff = flt(Math.ceil(natural_total) - natural_total, 2);

        frm.set_value("roundoff", roundoff);
    }

    let final_gt = flt(natural_total + roundoff, 2);
    frm.set_value("grand_total", final_gt);

    // Update balance_amount
    if (frm.fields_dict.balance_amount) {
        let paid = flt(frm.doc.paid_amount || 0, 2);
        frm.set_value('balance_amount', flt(final_gt - paid, 2));
    }

    frm.refresh_field("total_qty");
    frm.refresh_field("total_amount");
    frm.refresh_field("roundoff");
    frm.refresh_field("grand_total");
    if (frm.fields_dict.balance_amount) {
        frm.refresh_field("balance_amount");
    }
}
