// Copyright (c) 2025, deepak and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Employee", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('Employee', {
    onload(frm) {
        const restricted_fields = [
            "basic_pay",
            "hra",
            "conveyance_allowances",
            "medical_allowances",
            "other_allowances",
            "pf",
            "health_insurance",
            "professional_tax",
            "loan_recovery",
            "employee_id",
            "date_of_joining",
            "pf_number",
            "esi_no",
            "status",
            "user",
            "bank_account",
            "bank_name",
            "office_phone_number",
            "department",
            "designation"
        ];

        // Check if current user has the HR role
        const is_hr = frappe.user.has_role('HR');

        // Loop through all restricted fields
        restricted_fields.forEach(field => {
            frm.set_df_property(field, 'read_only', is_hr ? 0 : 1);
        });
    },
    refresh(frm) {
        // Attach a live input listener to CTC field
        const ctc_input = frm.fields_dict.ctc?.$input;
        if (ctc_input && !ctc_input.attr("data-live-ctc")) {
            ctc_input.attr("data-live-ctc", "1"); // prevent double-binding

            ctc_input.on("input", frappe.utils.debounce(async function () {
                await calculate_ctc_breakdown(frm);
            }, 500)); // waits 0.5s after typing stops
        }
    },
    ctc: async function(frm) {
        await calculate_ctc_breakdown(frm);
    }
});


// ================= Helper Function =================
async function calculate_ctc_breakdown(frm) {
    if (!frm.doc.ctc) return;

    const ctc = flt(frm.doc.ctc);

    // Fetch all Salary Structure Components
    const components = await frappe.db.get_list("Salary Structure Component", {
        fields: ["component_name", "field_name", "type", "percentage", "static_amount"],
        limit: 100
    });

    if (!components || !components.length) {
        frappe.msgprint("No salary components found in Salary Structure Component Doctype.");
        return;
    }

    // Reset salary-related fields to 0
    const salary_fields = components.map(c => c.field_name);
    salary_fields.forEach(field => {
        if (frm.fields_dict[field]) frm.set_value(field, 0);
    });

    // Initialize totals
    let total_earnings = 0;
    let total_deductions = 0;

    // Calculate per component
    for (let comp of components) {
        const field = comp.field_name;
        let value = 0;

        // If static_amount exists and > 0 → use it, else calculate from %
        if (flt(comp.static_amount) > 0) {
            value = flt(comp.static_amount);
        } else if (flt(comp.percentage) > 0) {
            value = ctc * flt(comp.percentage) / 100;
        }

        if (frm.fields_dict[field]) {
            frm.set_value(field, value);
        }

        // Accumulate totals
        if (comp.type === "Earnings") total_earnings += value;
        else if (comp.type === "Deduction") total_deductions += value;
    }

    // Optional: calculate net salary from totals
    const net_salary = total_earnings - total_deductions;

    // Update optional summary fields if you have them
    if (frm.fields_dict.total_earnings) frm.set_value("total_earnings", total_earnings);
    if (frm.fields_dict.total_deductions) frm.set_value("total_deductions", total_deductions);
    if (frm.fields_dict.net_salary) frm.set_value("net_salary", net_salary);

    // Live update alert
    // frappe.show_alert({
    //     message: `CTC breakdown updated!<br>Total Earnings: ₹${total_earnings.toFixed(2)}<br>Deductions: ₹${total_deductions.toFixed(2)}<br>Net Salary: ₹${net_salary.toFixed(2)}`,
    //     indicator: "green"
    // });
}
