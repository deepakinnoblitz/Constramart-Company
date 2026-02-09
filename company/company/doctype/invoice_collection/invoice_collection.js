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

        // Auto-calculate amount pending on input
        if (frm.fields_dict.amount_collected) {
            $(frm.fields_dict.amount_collected.input).on("input", function () {
                const pay = frm.doc.amount_to_pay || 0;
                const collected_now = flt($(this).val());
                frm.set_value("amount_pending", pay - collected_now);
            });
        }
        if (frm.is_new()) {
            frm.set_query("invoice", function () {
                return {
                    filters: {
                        "balance_amount": [">", 0]
                    },
                };
            });
        }
    },

    invoice(frm) {
        toggle_advance_field(frm);

        if (frm.doc.invoice) {
            frappe.db.get_doc("Invoice", frm.doc.invoice).then(invoice_doc => {
                frm.set_value("customer_id", invoice_doc.customer_id);

                // Get total already collected for this invoice
                frappe.db.get_list("Invoice Collection", {
                    filters: { invoice: frm.doc.invoice },
                    fields: ["amount_collected"]
                }).then(existing => {
                    let total_collected = 0;
                    if (existing && existing.length) {
                        total_collected = existing.reduce((sum, r) => sum + (r.amount_collected || 0), 0);
                    }

                    const remaining = invoice_doc.grand_total - total_collected;
                    frm.set_value("amount_to_pay", remaining);

                    // Initial pending = remaining - this collection (usually 0 on load)
                    const collected_now = frm.doc.amount_collected || 0;
                    frm.set_value("amount_pending", remaining - collected_now);
                });
            });
        }
    },

    is_advance(frm) {
        if (frm.doc.is_advance) {
            frappe.msgprint({
                title: __("Advance Payment"),
                message: __("This payment will be recorded as an advance and can only be set for the first collection on this invoice."),
                indicator: "blue"
            });
        }
    }
});

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
