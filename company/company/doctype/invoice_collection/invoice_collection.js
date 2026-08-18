frappe.ui.form.on("Invoice Collection", {
    refresh(frm) {
        toggle_advance_field(frm);

        if (!frm.is_new()) {
            // Check if this is the last collection for the invoice
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Invoice Collection",
                    filters: {
                        invoice: frm.doc.invoice,
                        creation: [">", frm.doc.creation],
                        name: ["!=", frm.doc.name]
                    },
                    limit: 1
                },
                callback: function (r) {
                    if (r.message && r.message.length > 0) {
                        // There are newer collections. Find the "last" one to show in message.
                        frappe.call({
                            method: "frappe.client.get_list",
                            args: {
                                doctype: "Invoice Collection",
                                filters: { invoice: frm.doc.invoice },
                                order_by: "creation desc",
                                limit: 1
                            },
                            callback: function (resp) {
                                if (resp.message && resp.message.length > 0) {
                                    const latest_invc = resp.message[0].name;
                                    frm.disable_save();
                                    frm.set_intro(__("Only the last collection ({0}) for an invoice can be edited or deleted.", [latest_invc]), "red");
                                    frm.set_read_only();
                                }
                            }
                        });
                    }
                }
            });
        }

        // Show indicator for advance payments
        if (frm.doc.is_advance) {
            frm.set_intro(__("This is an Advance Payment"), "blue");
        }

        // Auto-calculate breakdown on input
        if (frm.fields_dict.amount_collected) {
            $(frm.fields_dict.amount_collected.input).on("input", function () {
                recalculate_breakdown(frm);
            });
        }
    },

    invoice(frm) {
        toggle_advance_field(frm);

        if (frm.doc.invoice) {
            frappe.db.get_doc("Invoice", frm.doc.invoice).then(invoice_doc => {
                frm.set_value("customer_id", invoice_doc.customer_id);

                frappe.db.get_list("Invoice Collection", {
                    filters: { invoice: frm.doc.invoice },
                    fields: ["amount_collected", "advance_adjusted", "opening_balance_deducted", "excess_amount"]
                }).then(existing => {
                    let total_applied = 0;
                    if (existing && existing.length) {
                        total_applied = existing.reduce((sum, r) => sum + (flt(r.amount_collected) + flt(r.advance_adjusted) + flt(r.opening_balance_deducted) - flt(r.excess_amount)), 0);
                    }

                    const remaining = invoice_doc.grand_total - total_applied;
                    frm.set_value("amount_to_pay", Math.max(0, remaining));

                    // Fetch customer balances and recalculate
                    frm.trigger("fetch_balances");
                });
            });
        }
    },

    use_opening_balance(frm) {
        recalculate_breakdown(frm);
    },

    fetch_balances(frm) {
        if (!frm.doc.customer_id) return;
        frappe.call({
            method: "company.company.api.get_customer_balances",
            args: { customer_id: frm.doc.customer_id },
            callback: function (r) {
                if (r.message) {
                    frm.set_value("available_opening_balance", r.message.opening_balance || 0);
                    frm.set_value("available_advance", r.message.available_advance || 0);
                    recalculate_breakdown(frm);
                }
            }
        });
    },

    is_advance(frm) {
        recalculate_breakdown(frm);
        if (frm.doc.is_advance) {
            frappe.msgprint({
                title: __("Advance Payment"),
                message: __("This payment will be recorded as an advance and can only be set for the first collection on this invoice."),
                indicator: "blue"
            });
        }
    },
    after_save: function (frm) {
        if (frm.doc.invoice) {
            frappe.show_alert({
                message: __("Invoice {0} updated", [frm.doc.invoice]),
                indicator: "green"
            });

            // Redirect back to Invoice and reload it
            frappe.set_route("Form", "Invoice", frm.doc.invoice).then(() => {
                const parent_frm = cur_frm;
                if (parent_frm && parent_frm.doctype === "Invoice" && parent_frm.docname === frm.doc.invoice) {
                    parent_frm.reload_doc();
                }
            });
        }
    }
});

function recalculate_breakdown(frm) {
    const pay = flt(frm.doc.amount_to_pay);
    const avail_adv = flt(frm.doc.available_advance);
    const avail_ob = flt(frm.doc.available_opening_balance);

    if (frm.doc.is_advance) {
        frm.set_value("advance_adjusted", 0);
        frm.set_value("opening_balance_deducted", 0);
        frm.set_value("excess_amount", 0);
        const collected = flt(frm.doc.amount_collected);
        frm.set_value("amount_pending", pay - collected);
        return;
    }

    // Step 1: Advance Adjustment
    const adv_adj = Math.min(avail_adv, pay);
    frm.set_value("advance_adjusted", adv_adj);
    let rem_after_adv = pay - adv_adj;

    // Step 2: Opening Balance Deduction
    let ob_deducted = 0;
    if (frm.doc.use_opening_balance) {
        ob_deducted = Math.min(avail_ob, rem_after_adv);
    }
    frm.set_value("opening_balance_deducted", ob_deducted);
    let rem_after_ob = rem_after_adv - ob_deducted;

    // Step 3: Normal Collection & Excess
    const collected = flt(frm.doc.amount_collected);
    let pending = rem_after_ob - collected;
    let excess = 0;
    if (pending < 0) {
        excess = Math.abs(pending);
        pending = 0;
    }
    frm.set_value("excess_amount", excess);
    frm.set_value("amount_pending", pending);
}

function toggle_advance_field(frm) {
    if (!frm.doc.invoice) {
        // No invoice selected - hide advance checkbox
        frm.set_df_property("is_advance", "hidden", 1);
        return;
    }

    // Check if this invoice already has collections
    frappe.call({
        method: "frappe.client.get_count",
        args: {
            doctype: "Invoice Collection",
            filters: {
                invoice: frm.doc.invoice,
                name: ["!=", frm.doc.name || ""]  // Exclude current doc if editing
            }
        },
        callback: function (r) {
            if (r.message > 0) {
                // Invoice already has collections - hide and uncheck advance
                frm.set_df_property("is_advance", "hidden", 1);
                frm.set_value("is_advance", 0);
            } else {
                // First collection for this invoice - show advance checkbox
                frm.set_df_property("is_advance", "hidden", 0);
            }
        }
    });
}
