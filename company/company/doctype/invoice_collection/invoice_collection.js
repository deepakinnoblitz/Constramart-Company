frappe.ui.form.on("Invoice Collection", {
    setup(frm) {
        frm.set_query("invoice", function () {
            let filters = {
                balance_amount: [">", 0]
            };
            if (frm.doc.customer_id) {
                filters["customer_id"] = frm.doc.customer_id;
            }
            return {
                filters: filters
            };
        });
    },

    before_save(frm) {
        if (flt(frm.doc.excess_amount) > 0 && !frm._excess_confirmed) {
            frappe.validated = false;
            frappe.confirm(
                __("An excess collection of <b>{0}</b> will be credited to the customer's Opening Balance.<br><br>Do you want to proceed?", [format_currency(frm.doc.excess_amount)]),
                function () {
                    frm._excess_confirmed = true;
                    frm.save();
                },
                function () {
                    frm._excess_confirmed = false;
                }
            );
        } else {
            frm._excess_confirmed = false;
        }
    },

    refresh(frm) {
        toggle_advance_field(frm);

        if (!frm.is_new() && !frm.doc.is_advance) {
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

        // Hide Opening Balance Details section for Advance Collections
        frm.set_df_property("opening_balance_details_section", "hidden", frm.doc.is_advance ? 1 : 0);

        // Lock Advance Payment collections from manual editing
        if (!frm.is_new() && frm.doc.is_advance) {
            frm.disable_save();
            frm.set_read_only();
            if (frm.doc.invoice) {
                frm.set_intro(__("This is an Advance Payment linked to Sales Bill {0}. It cannot be edited directly.", [frm.doc.invoice]), "blue");
            } else {
                frm.set_intro(__("This is an Advance Payment entry and cannot be edited directly."), "blue");
            }
        } else if (frm.doc.is_advance) {
            frm.set_intro(__("This is an Advance Payment"), "blue");
        }

        // Auto-calculate breakdown on input
        if (frm.fields_dict.amount_collected) {
            $(frm.fields_dict.amount_collected.input).on("input", function () {
                recalculate_breakdown(frm);
            });
        }

        if (frm.doc.invoice) {
            frm.trigger("invoice");
        }
    },

    invoice(frm) {
        toggle_advance_field(frm);

        if (!frm.doc.invoice) {
            frm.set_value("customer_id", "");
            frm.set_value("customer_name", "");
            frm.set_value("amount_to_pay", 0);
            frm.set_value("available_opening_balance", 0);
            frm.set_value("available_advance", 0);
            recalculate_breakdown(frm);
            return;
        }

        frappe.db.get_doc("Invoice", frm.doc.invoice).then(invoice_doc => {
            if (frm.is_new() && flt(invoice_doc.balance_amount) <= 0) {
                frappe.msgprint({
                    title: __("Fully Paid Sales Bill"),
                    message: __("Sales Bill <b>{0}</b> is already fully paid (Balance: ₹0.00). Please select an unpaid invoice.", [frm.doc.invoice]),
                    indicator: "orange"
                });
                frm.set_value("invoice", "");
                frm.set_value("customer_id", "");
                frm.set_value("customer_name", "");
                frm.set_value("amount_to_pay", 0);
                frm.set_value("available_opening_balance", 0);
                frm.set_value("available_advance", 0);
                recalculate_breakdown(frm);
                return;
            }

            frm.set_value("customer_id", invoice_doc.customer_id);

            let filters = { invoice: frm.doc.invoice };
            if (frm.doc.name && !frm.is_new()) {
                filters["name"] = ["!=", frm.doc.name];
            }

            frappe.db.get_list("Invoice Collection", {
                filters: filters,
                fields: ["amount_collected", "advance_adjusted", "opening_balance_deduction", "excess_amount", "is_advance"]
            }).then(existing => {
                let total_applied = 0;
                if (existing && existing.length) {
                    total_applied = existing.reduce((sum, r) => {
                        if (r.is_advance) {
                            return sum + flt(r.amount_collected);
                        } else {
                            return sum + (flt(r.amount_collected) + flt(r.advance_adjusted) - flt(r.excess_amount));
                        }
                    }, 0);
                }

                const remaining = invoice_doc.grand_total - total_applied;
                frm.set_value("amount_to_pay", Math.max(0, remaining));

                // Fetch customer balances and recalculate
                frm.trigger("fetch_balances");
            });
        });
    },

    use_opening_balance(frm) {
        if (!frm.doc.use_opening_balance) {
            frm.set_value("opening_balance_deduction", 0);
            frm.set_value("amount_collected_using_opening_balance", 0);
        }
        recalculate_breakdown(frm);
    },

    opening_balance_deduction(frm) {
        const avail_ob = flt(frm.doc.available_opening_balance);
        const pay = flt(frm.doc.amount_to_pay);
        const adv_adj = flt(frm.doc.advance_adjusted);
        const max_allowed = Math.min(avail_ob, Math.max(0, pay - adv_adj));

        let current_ob = flt(frm.doc.opening_balance_deduction);
        if (current_ob > max_allowed) {
            current_ob = max_allowed;
            frm.set_value("opening_balance_deduction", current_ob);
        }

        frm.set_value("amount_collected_using_opening_balance", current_ob);
        recalculate_breakdown(frm);
    },

    amount_collected_normally(frm) {
        recalculate_breakdown(frm);
    },

    fetch_balances(frm) {
        if (!frm.doc.customer_id) return;
        frappe.call({
            method: "company.company.api.get_customer_balances",
            args: {
                customer_id: frm.doc.customer_id,
                current_collection: frm.doc.name || ""
            },
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
    before_save(frm) {
        if (frm.doc.amount_collected == null || frm.doc.amount_collected === "") {
            frm.set_value("amount_collected", 0);
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
                setTimeout(() => {
                    if (cur_frm && cur_frm.doctype === "Invoice") {
                        cur_frm.reload_doc();
                    }
                }, 500);
            });
        }
    }
});

function recalculate_breakdown(frm) {
    const pay = flt(frm.doc.amount_to_pay);
    const avail_adv = flt(frm.doc.available_advance);
    const avail_ob = flt(frm.doc.available_opening_balance);

    frm.set_df_property("opening_balance_details_section", "hidden", frm.doc.is_advance ? 1 : 0);

    if (frm.doc.is_advance) {
        const collected = flt(frm.doc.amount_collected_normally || frm.doc.amount_collected);
        frm.set_value("advance_adjusted", collected);
        frm.set_value("opening_balance_deduction", 0);
        frm.set_value("amount_collected_using_opening_balance", 0);
        frm.set_value("excess_amount", 0);
        frm.set_value("amount_collected", collected);
        frm.set_value("amount_pending", Math.max(0, pay - collected));
        return;
    }

    // Step 1: Advance Adjustment
    const adv_adj = Math.min(avail_adv, pay);
    frm.set_value("advance_adjusted", adv_adj);
    let rem_after_adv = pay - adv_adj;

    // Step 2: Opening Balance Deduction
    let ob_deducted = 0;
    if (frm.doc.use_opening_balance) {
        let current_val = flt(frm.doc.opening_balance_deduction || 0);
        ob_deducted = Math.min(avail_ob, Math.min(rem_after_adv, current_val));
    } else {
        ob_deducted = 0;
        frm.set_value("opening_balance_deduction", 0);
    }
    frm.set_df_property("amount_collected_using_opening_balance", "hidden", frm.doc.use_opening_balance ? 0 : 1);
    frm.set_value("amount_collected_using_opening_balance", ob_deducted);
    let rem_after_ob = rem_after_adv - ob_deducted;

    // Step 3: Normal Collection & Total Amount Collected Calculation
    const collected_normally = flt(frm.doc.amount_collected_normally || 0);
    const total_collected = ob_deducted + collected_normally;
    frm.set_value("amount_collected", total_collected);

    let pending = rem_after_ob - collected_normally;
    let excess = 0;
    if (pending < 0) {
        excess = Math.abs(pending);
        pending = 0;
    }
    frm.set_value("excess_amount", excess);
    frm.set_value("amount_pending", pending);
}

function toggle_advance_field(frm) {
    if (frm.is_new()) {
        // Hide Is Advance checkbox on new collection forms
        frm.set_df_property("is_advance", "hidden", 1);
        return;
    }

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
