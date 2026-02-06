frappe.ui.form.on("Purchase Collection", {
    purchase: function (frm) {
        if (frm.doc.purchase) {
            frappe.db.get_doc("Purchase", frm.doc.purchase).then(purchase_doc => {
                frm.set_value("vendor_id", purchase_doc.vendor_id);

                // Get total already paid for this purchase
                frappe.db.get_list("Purchase Collection", {
                    filters: { purchase: frm.doc.purchase },
                    fields: ["amount_paid"]
                }).then(existing => {
                    let total_paid = 0;
                    if (existing && existing.length) {
                        total_paid = existing.reduce((sum, r) => sum + (r.amount_paid || 0), 0);
                    }

                    const remaining = purchase_doc.grand_total - total_paid;
                    frm.set_value("amount_to_pay", remaining);

                    // Initial pending = remaining - this payment (usually 0 on load)
                    const paid_now = frm.doc.amount_paid || 0;
                    frm.set_value("amount_pending", remaining - paid_now);
                });
            });
        }
    },
    refresh: function (frm) {
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
                        // There are newer collections. Find the "last" one to show in message.
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

        if (frm.fields_dict.amount_paid) {
            $(frm.fields_dict.amount_paid.input).on("input", function () {
                const pay = frm.doc.amount_to_pay || 0;
                const paid_now = flt($(this).val());
                frm.set_value("amount_pending", pay - paid_now);
            });
        }
    }
});
