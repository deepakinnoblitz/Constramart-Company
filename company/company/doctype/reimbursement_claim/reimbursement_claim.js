frappe.ui.form.on("Reimbursement Claim", {

    refresh(frm) {
        evaluate_visibility(frm);

        $(".form-message-container").hide();
    },

    workflow_state(frm) {
        evaluate_visibility(frm);
    },

    after_workflow_action(frm) {
        frm.reload_doc();
    },

    after_save(frm) {
        auto_submit(frm);
    }

});

function auto_submit(frm) {
    if (frm.doc.docstatus === 0) {

        frappe.call({
            method: "frappe.client.submit",
            args: {
                doc: frm.doc
            },
            callback: function (r) {
                if (!r.exc) {

                    // ⭐ SUCCESS POPUP
                    frappe.msgprint({
                        title: __('Success'),
                        indicator: 'green',
                        message: __('Reimbursement Claim submitted successfully!')
                    });

                    frm.reload_doc();  // refresh updated state
                }
            }
        });
    }
}


function evaluate_visibility(frm) {
    let state = frm.doc.workflow_state;

    // 1️⃣ Employee logic
    if (frappe.user_roles.includes("Employee")) {

        // Employee sees section ONLY when Paid
        if (state === "Paid") {
            return toggle_settlement_section(frm, true);
        } else {
            return toggle_settlement_section(frm, false);
        }
    }

    // 2️⃣ HR logic – sees in Approved or Paid
    if (["Approved", "Paid"].includes(state)) {
        toggle_settlement_section(frm, true);
    } else {
        toggle_settlement_section(frm, false);
    }
}


function toggle_settlement_section(frm, show) {
    frm.toggle_display("settlement_details_section", show);

    // Auto-hide all children under the section
    let fields = [
        "approved_by",
        "paid_by",
        "approver_comments",
        "column_break_3",
        "paid",
        "paid_date",
        "payment_reference",
        "payment_proof",
        "policy_violation"
    ];

    fields.forEach(field => {
        if (frm.fields_dict[field]) {
            frm.toggle_display(field, show);
        }
    });
}
