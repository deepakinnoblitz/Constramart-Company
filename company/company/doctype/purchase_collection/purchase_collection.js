frappe.ui.form.on("Purchase Collection", {
    setup(frm) {
        frm.set_query("purchase", function () {
            let filters = {
                balance_amount: [">", 0]
            };
            if (frm.doc.vendor_id) {
                filters["vendor_id"] = frm.doc.vendor_id;
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
                __("An excess payment of <b>{0}</b> will be credited to the vendor's Opening Balance.<br><br>Do you want to proceed?", [format_currency(frm.doc.excess_amount)]),
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

        if (!frm.is_new()) {
            // Check if this is the last collection for the purchase order
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Purchase Collection",
                    filters: {
                        purchase: frm.doc.purchase,
                        creation: [">", frm.doc.creation],
                        name: ["!=", frm.doc.name]
                    },
                    limit: 1
                },
                callback: function (r) {
                    if (r.message && r.message.length > 0) {
                        frappe.call({
                            method: "frappe.client.get_list",
                            args: {
                                doctype: "Purchase Collection",
                                filters: { purchase: frm.doc.purchase },
                                order_by: "creation desc",
                                limit: 1
                            },
                            callback: function (resp) {
                                if (resp.message && resp.message.length > 0) {
                                    const latest_purc = resp.message[0].name;
                                    frm.disable_save();
                                    frm.set_intro(__("Only the last collection ({0}) for a purchase order can be edited or deleted.", [latest_purc]), "red");
                                    frm.set_read_only();
                                }
                            }
                        });
                    }
                }
            });
        }

        // Lock Advance Payment collections from manual editing
        if (!frm.is_new() && frm.doc.is_advance) {
            frm.disable_save();
            frm.set_read_only();
            if (frm.doc.purchase) {
                frm.set_intro(__("This is an Advance Payment linked to Purchase Bill {0}. It cannot be edited directly.", [frm.doc.purchase]), "blue");
            } else {
                frm.set_intro(__("This is an Advance Payment entry and cannot be edited directly."), "blue");
            }
        } else if (frm.doc.is_advance) {
            frm.set_intro(__("This is an Advance Payment"), "blue");
        }
    },

    purchase: function (frm) {
        if (!frm.doc.purchase) {
            frm.set_value("vendor_id", "");
            frm.set_value("vendor_name", "");
            frm.set_value("amount_to_pay", 0);
            frm.set_value("available_opening_balance", 0);
            frm.set_value("use_opening_balance", 0);
            frm.set_value("opening_balance_deduction", 0);
            frm.set_value("amount_paid_using_opening_balance", 0);
            frm.set_value("amount_paid_normally", 0);
            frm.set_value("amount_paid", 0);
            frm.set_value("amount_pending", 0);
            frm.set_value("excess_amount", 0);
            return;
        }

        frappe.db.get_doc("Purchase", frm.doc.purchase).then(purchase_doc => {
            if (flt(purchase_doc.balance_amount) <= 0) {
                frappe.msgprint({
                    title: __("Purchase Already Paid"),
                    indicator: "orange",
                    message: __("Purchase Bill <b>{0}</b> is already fully paid.", [frm.doc.purchase])
                });
                frm.set_value("purchase", "");
                frm.set_value("vendor_id", "");
                frm.set_value("vendor_name", "");
                frm.set_value("amount_to_pay", 0);
                frm.set_value("available_opening_balance", 0);
                frm.set_value("use_opening_balance", 0);
                frm.set_value("opening_balance_deduction", 0);
                frm.set_value("amount_paid_using_opening_balance", 0);
                frm.set_value("amount_paid_normally", 0);
                frm.set_value("amount_paid", 0);
                frm.set_value("amount_pending", 0);
                frm.set_value("excess_amount", 0);
                return;
            }

            frm.set_value("vendor_id", purchase_doc.vendor_id);
            frm.set_value("vendor_name", purchase_doc.vendor_name);

            // Fetch previous collections for this purchase
            let filters = { purchase: frm.doc.purchase };
            if (frm.doc.name && !frm.is_new()) {
                filters["name"] = ["!=", frm.doc.name];
            }

            frappe.db.get_list("Purchase Collection", {
                filters: filters,
                fields: ["amount_paid", "advance_adjusted", "opening_balance_deduction", "excess_amount", "is_advance"]
            }).then(existing => {
                let total_applied = 0;
                if (existing && existing.length) {
                    total_applied = existing.reduce((sum, r) => {
                        if (r.is_advance) {
                            return sum + flt(r.amount_paid);
                        } else {
                            return sum + (flt(r.amount_paid) + flt(r.advance_adjusted) - flt(r.excess_amount));
                        }
                    }, 0);
                }

                const remaining = purchase_doc.grand_total - total_applied;
                frm.set_value("amount_to_pay", Math.max(0, remaining));

                // Fetch vendor balances and recalculate
                frm.trigger("fetch_balances");
            });
        });
    },

    use_opening_balance(frm) {
        if (!frm.doc.use_opening_balance) {
            frm.set_value("opening_balance_deduction", 0);
            frm.set_value("amount_paid_using_opening_balance", 0);
        }
        recalculate_breakdown(frm);
    },

    opening_balance_deduction(frm) {
        const avail_ob = flt(frm.doc.available_opening_balance);
        const pay = flt(frm.doc.amount_to_pay);
        let entered_val = flt(frm.doc.opening_balance_deduction);

        if (entered_val < 0) {
            entered_val = 0;
        }

        const max_allowed = Math.min(avail_ob, pay);
        if (entered_val > max_allowed) {
            frappe.msgprint({
                title: __("Limit Exceeded"),
                indicator: "orange",
                message: __("Opening balance deduction cannot exceed {0}.", [format_currency(max_allowed)])
            });
            entered_val = max_allowed;
        }

        frm.set_value("opening_balance_deduction", entered_val);
        recalculate_breakdown(frm);
    },

    amount_paid_normally(frm) {
        recalculate_breakdown(frm);
    },

    fetch_balances(frm) {
        const vendor_id = frm.doc.vendor_id;
        if (!vendor_id) {
            frm.set_value("available_opening_balance", 0);
            recalculate_breakdown(frm);
            return;
        }

        frappe.call({
            method: "frappe.client.get",
            args: { doctype: "Customer", name: vendor_id },
            callback: function (r) {
                if (r.message) {
                    const cust = r.message;
                    const avail_ob = flt(cust.opening_balance || 0);

                    frm.set_value("available_opening_balance", avail_ob);
                    if (avail_ob <= 0) {
                        frm.set_value("use_opening_balance", 0);
                        frm.set_value("opening_balance_deduction", 0);
                    }
                    recalculate_breakdown(frm);
                }
            }
        });
    },

    after_save: function (frm) {
        if (frm.doc.purchase) {
            frappe.show_alert({
                message: __("Purchase {0} updated", [frm.doc.purchase]),
                indicator: "green"
            });

            frappe.set_route("Form", "Purchase", frm.doc.purchase).then(() => {
                const parent_frm = cur_frm;
                if (parent_frm && parent_frm.doctype === "Purchase" && parent_frm.docname === frm.doc.purchase) {
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
        const paid = flt(frm.doc.amount_paid_normally || frm.doc.amount_paid);
        frm.set_value("advance_adjusted", paid);
        frm.set_value("opening_balance_deduction", 0);
        frm.set_value("amount_paid_using_opening_balance", 0);
        frm.set_value("excess_amount", 0);
        frm.set_value("amount_paid", paid);
        frm.set_value("amount_pending", Math.max(0, pay - paid));
        return;
    }

    // Hide Advance fields
    frm.set_df_property("available_advance", "hidden", 1);
    frm.set_df_property("advance_adjusted", "hidden", 1);

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
    frm.set_df_property("amount_paid_using_opening_balance", "hidden", frm.doc.use_opening_balance ? 0 : 1);
    frm.set_value("amount_paid_using_opening_balance", ob_deducted);
    let rem_after_ob = rem_after_adv - ob_deducted;

    // Step 3: Normal Collection & Total Amount Paid Calculation
    const paid_normally = flt(frm.doc.amount_paid_normally || 0);
    const total_paid = ob_deducted + paid_normally;
    frm.set_value("amount_paid", total_paid);

    let pending = rem_after_ob - paid_normally;
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
        frm.set_df_property("is_advance", "hidden", 1);
        return;
    }

    if (!frm.doc.purchase) {
        frm.set_df_property("is_advance", "hidden", 1);
        return;
    }

    frappe.call({
        method: "frappe.client.get_count",
        args: {
            doctype: "Purchase Collection",
            filters: {
                purchase: frm.doc.purchase,
                name: ["!=", frm.doc.name || ""]
            }
        },
        callback: function (r) {
            if (r.message > 0) {
                frm.set_df_property("is_advance", "hidden", 1);
                frm.set_value("is_advance", 0);
            } else {
                frm.set_df_property("is_advance", "hidden", 0);
            }
        }
    });
}
