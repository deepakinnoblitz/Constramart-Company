frappe.ui.form.on("Leads", {
    refresh(frm) {

        // Show button only if not already converted and not closed
        if (!frm.is_new() && frm.doc.status !== "Closed") {
            frappe.db.exists("Customer", { lead: frm.doc.name }).then(exists => {
                if (!exists) {
                    frm.add_custom_button("Convert to Customer", () => {
                        frappe.confirm(
                            `Are you sure you want to convert <b>${frm.doc.lead_name}</b> to a Customer?`,
                            () => {
                                // YES
                                frappe.call({
                                    method: "company.company.api.convert_lead_to_customer",
                                    args: {
                                        lead_name: frm.doc.name
                                    },
                                    freeze: true,
                                    freeze_message: "Converting Lead to Customer...",
                                    callback(r) {
                                        if (r.message) {
                                            frappe.msgprint({
                                                title: "Success",
                                                message: "Customer created successfully",
                                                indicator: "green"
                                            });

                                            // Redirect to Customer
                                            frappe.set_route("Form", "Customer", r.message);
                                        }
                                    }
                                });
                            },
                            () => {
                                // NO
                                frappe.msgprint("Conversion cancelled");
                            }
                        );
                    });
                }
            });
        }

        // ✅ Set default Country & State ONLY for new Lead
        if (frm.is_new()) {
            if (!frm.doc.country) {
                frm.set_value("country", "India");
            }

            if (!frm.doc.state) {
                frm.set_value("state", "Tamil Nadu");
            }
        }

        // 2️⃣ WhatsApp Button
        if (frm.doc.phone_number) {
            let phone = frm.doc.phone_number.replace(/[^0-9]/g, "");
            if (!phone.startsWith("91")) phone = "91" + phone;

            frm.add_custom_button("WhatsApp", () => {
                let msg = `Hello ${frm.doc.lead_name}, regarding your inquiry about ${frm.doc.service}.`;
                let url = `https://wa.me/${phone}?text=${encodeURIComponent(msg)}`;
                window.open(url, "_blank");
            });
        }

        // 2.5️⃣ Load States on Refresh
        if (frm.doc.country) {
            frappe.call({
                method: "company.company.api.get_states",
                args: { country: frm.doc.country },
                callback(r) {
                    frm.set_df_property(
                        "state",
                        "options",
                        ["", ...(r.message || []), "Others"].join("\n")
                    );
                    frm.refresh_field("state");
                }
            });
        }

        // 3️⃣ Auto-load city
        if (frm.doc.country && frm.doc.state && frm.doc.state !== "Others") {
            frappe.call({
                method: "company.company.api.get_cities",
                args: {
                    country: frm.doc.country,
                    state: frm.doc.state
                },
                callback(r) {
                    frm.set_df_property(
                        "city",
                        "options",
                        ["", ...(r.message || []), "Others"].join("\n")
                    );
                    frm.refresh_field("city");
                }
            });
        }

        // 4️⃣ Restrict Followup Row Editing (Grid)
        const current_user = frappe.session.user;
        if (current_user !== "Administrator" && frm.doc.followup && frm.doc.followup.length > 0) {
            frm.fields_dict.followup.grid.grid_rows.forEach(row => {
                const owner = (row.doc.owner_name || "").trim();
                const user = (frappe.session.user || "").trim();

                // Clean up any old shield
                row.wrapper.find(".restricted-shield").remove();
                row.wrapper.off("click.restricted");

                if (owner && owner !== user) {
                    row.toggle_editable(false);

                    // CRITICAL: Ensure the row is the boundary for the absolute shield
                    row.wrapper.css("position", "relative");

                    // Hide management buttons
                    row.wrapper.find(".grid-static-col .row-check, .grid-remove-row").css("visibility", "hidden");

                    // Inject the transparent "Shield"
                    const $shield = $('<div class="restricted-shield"></div>').appendTo(row.wrapper);
                    $shield.css({
                        "position": "absolute",
                        "top": 0,
                        "left": 0,
                        "width": "100%",
                        "height": "110%", // Slightly oversized to cover the whole row height
                        "z-index": 9999, // Ensure it's on top of everything in the row
                        "cursor": "not-allowed",
                        "background": "transparent"
                    });

                    // Live Alert on shield click
                    $shield.on("click", (e) => {
                        frappe.show_alert({
                            message: __("Live: Row restricted. Only {0} can edit this followup.", [owner]),
                            indicator: "orange"
                        });
                        e.preventDefault();
                        e.stopPropagation();
                    });
                }
            });
        }

        // 5️⃣ Hide Followups Tab on New Lead
        frm.toggle_display("followups_tab", !frm.is_new());
        frm.toggle_display("followup", !frm.is_new());
    },

    before_save(frm) {
        // Client-side validation for row ownership before sending to server
        const current_user = frappe.session.user;
        if (current_user === "Administrator") return;

        if (frm.doc.followup) {
            frm.doc.followup.forEach(row => {
                // If the row exists (has a name) and is not owned by the current user
                if (row.name && row.owner_name && row.owner_name !== current_user) {
                    // Check if any restricted fields changed manually through console or other bypasses
                    // This is a safety layer
                }
            });
        }
    },

    country(frm) {
        if (!frm.doc.country) return;

        frappe.call({
            method: "company.company.api.get_states",
            args: { country: frm.doc.country },
            callback(r) {
                frm.set_df_property(
                    "state",
                    "options",
                    ["", ...(r.message || []), "Others"].join("\n")
                );
                frm.refresh_field("state");
            }
        });
    },

    state(frm) {
        if (!frm.doc.country || !frm.doc.state) return;

        if (frm.doc.state === "Others") {
            frm.set_df_property("city", "options", "Others");
            frm.refresh_field("city");
            return;
        }

        frappe.call({
            method: "company.company.api.get_cities",
            args: {
                country: frm.doc.country,
                state: frm.doc.state
            },
            callback(r) {
                frm.set_df_property(
                    "city",
                    "options",
                    ["", ...(r.message || []), "Others"].join("\n")
                );
                frm.refresh_field("city");
            }
        });
    }
});

// -----------------------------------------
// FOLLOWUP CHILD TABLE LOGIC
// -----------------------------------------
frappe.ui.form.on("Followup", {
    followup_add(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        // Set owner_name for new rows immediately
        frappe.model.set_value(cdt, cdn, "owner_name", frappe.session.user);
    },

    followup_on_form_render(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        const grid_row = frm.fields_dict.followup.grid.get_row(cdn);

        // Check ownership
        const current_user = frappe.session.user;
        const is_administrator = current_user === "Administrator";
        const is_not_owner = row.owner_name && row.owner_name !== current_user && !is_administrator;

        // Use the grid_row's form fields_dict for row-specific modal control
        if (grid_row.grid_form && grid_row.grid_form.fields_dict) {
            const fields_dict = grid_row.grid_form.fields_dict;

            // 1. Always lock the Owner Name field in the modal
            if (fields_dict.owner_name) {
                fields_dict.owner_name.set_read_only(true);
            }

            // 2. Lock other fields if not the owner
            const fields = ["followup_date", "lead_status", "remark"];
            fields.forEach(f => {
                if (fields_dict[f]) {
                    fields_dict[f].set_read_only(is_not_owner);
                }
            });
        }

        if (is_not_owner) {
            frappe.show_alert({
                message: __("Editing restricted: Row owned by {0}", [row.owner_name]),
                indicator: "orange"
            });
        }
    },

    before_followup_remove(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.owner_name && row.owner_name !== frappe.session.user) {
            frappe.msgprint(__("You cannot delete a followup created by {0}.", [row.owner_name]));
            frappe.validated = false;
            throw "Not allowed";
        }
    }
});
