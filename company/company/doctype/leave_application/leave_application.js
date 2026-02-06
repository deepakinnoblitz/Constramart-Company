frappe.ui.form.on("Leave Application", {
    from_date: function (frm) { frm.trigger("calculate_total_days"); },
    to_date: function (frm) { frm.trigger("calculate_total_days"); },
    half_day: function (frm) { frm.trigger("calculate_total_days"); },
    leave_type: function (frm) { frm.trigger("calculate_total_days"); },
    employee: function (frm) { frm.trigger("calculate_total_days"); },
    permission_hours: function (frm) { frm.trigger("calculate_total_days"); },

    calculate_total_days: function (frm) {

        if (!frm.doc.employee || !frm.doc.leave_type || !frm.doc.from_date || !frm.doc.to_date) {
            frm.set_value("total_days", 0);
            return;
        }

        // ---------- Permission Hours Validation ----------
        if (frm.doc.permission_hours && frm.doc.permission_hours < 10) {
            frappe.msgprint(__('Permission hours should be entered in minutes only.'));
            frm.set_value("permission_hours", 0);
            return;
        }

        // ---------- Total Days Calculation ----------
        let days = frappe.datetime.get_diff(frm.doc.to_date, frm.doc.from_date) + 1;

        // Apply half-day correctly: subtract 0.5 from total
        if (frm.doc.half_day) {
            days -= 0.5;   // <-- Correct behaviour
        }

        frm.set_value("total_days", days);

        // ---------- Check Leave Balance ----------
        frappe.call({
            method: "company.company.api.check_leave_balance",
            args: {
                employee: frm.doc.employee,
                leave_type: frm.doc.leave_type,
                from_date: frm.doc.from_date,
                to_date: frm.doc.to_date,
                half_day: frm.doc.half_day ? 1 : 0,
                permission_hours: frm.doc.permission_hours
            },
            callback: function (r) {
                const res = r.message || {};

                if (res.allowed === false) {
                    frappe.msgprint(
                        __('Not enough leave balance.<br>Available: '
                            + res.remaining + ' ' + res.unit + '<br>Requested: '
                            + res.requested + ' ' + res.unit)
                    );
                    frm.set_value("total_days", 0);
                }
            }
        });
    },
    refresh(frm) {
        // Remove specific workflow actions from Actions menu after they are added
        // Wait for workflow engine, then cleanup and hide empty group
        setTimeout(() => {
            if (frm.page.actions) {
                // Remove listed items
                frm.page.actions.find('li').each(function () {
                    const label = $(this).find('.menu-item-label').text().trim();
                    if (["Ask Clarification", "Reply", "Reply to HR", "Help"].includes(label)) {
                        $(this).remove();
                    }
                });

                // Hide the whole group if no functional items (labels) are left
                // This preserves dividers/empty tags while hiding the button if useless
                if (frm.page.actions.find('.menu-item-label').length === 0) {
                    frm.page.actions_btn_group.hide();
                } else {
                    frm.page.actions_btn_group.show();
                }
            }
        }, 300);

        // HR → Reply to Employee
        if (
            frm.doc.workflow_state === "Pending" &&
            frappe.user.has_role("HR")
        ) {
            frm.add_custom_button(
                "Reply to Employee",
                () => {
                    const rounds = ["hr_query", "hr_query_2", "hr_query_3", "hr_query_4", "hr_query_5"];
                    let next_field = rounds.find(field => !frm.doc[field]);

                    if (!next_field) {
                        frappe.msgprint(__("Maximum communication rounds (5) reached."));
                        return;
                    }

                    frappe.prompt(
                        [
                            {
                                fieldname: "query",
                                label: "HR Question",
                                fieldtype: "Small Text",
                                reqd: 1
                            }
                        ],
                        (values) => {
                            frm.set_value(next_field, values.query);

                            frappe.confirm(
                                "Do you want to send this clarification request to the employee?",
                                () => {
                                    const save_action = frm.doc.docstatus === 1 ? 'Update' : 'Save';
                                    frm.save(save_action).then(() => {
                                        frappe.xcall("frappe.model.workflow.apply_workflow", {
                                            doc: frm.doc,
                                            action: "Ask Clarification"
                                        }).then(doc => {
                                            frappe.model.sync(doc);
                                            frm.refresh();
                                        });
                                    });
                                },
                                () => {
                                    frm.reload_doc();
                                }
                            );
                        },
                        "Reply to Employee"
                    );
                },
                null
            );
            frm.change_custom_button_type("Reply to Employee", null, "primary");
        }

        // Employee → Reply (Prompt)
        if (
            frm.doc.workflow_state === "Clarification Requested" &&
            frappe.user.has_role("Employee")
        ) {
            frm.add_custom_button(
                "Reply to HR",
                () => {
                    const hr_rounds = ["hr_query", "hr_query_2", "hr_query_3", "hr_query_4", "hr_query_5"];
                    const emp_rounds = ["employee_reply", "employee_reply_2", "employee_reply_3", "employee_reply_4", "employee_reply_5"];

                    // Find the last filled HR query that doesn't have an employee reply yet
                    let round_index = -1;
                    for (let i = 0; i < 5; i++) {
                        if (frm.doc[hr_rounds[i]] && !frm.doc[emp_rounds[i]]) {
                            round_index = i;
                            break;
                        }
                    }

                    if (round_index === -1) {
                        frappe.msgprint(__("No pending HR queries to reply to."));
                        return;
                    }

                    let next_field = emp_rounds[round_index];

                    frappe.prompt(
                        [
                            {
                                fieldname: "reply",
                                label: "Your Reply",
                                fieldtype: "Small Text",
                                reqd: 1
                            }
                        ],
                        (values) => {
                            frm.set_value(next_field, values.reply);

                            frappe.confirm(
                                "Are you sure you want to submit your reply to HR?",
                                () => {
                                    const save_action = frm.doc.docstatus === 1 ? 'Update' : 'Save';
                                    frm.save(save_action).then(() => {
                                        frappe.xcall("frappe.model.workflow.apply_workflow", {
                                            doc: frm.doc,
                                            action: "Reply"
                                        }).then(doc => {
                                            frappe.model.sync(doc);
                                            frm.refresh();
                                        });
                                    });
                                },
                                () => {
                                    frm.reload_doc();
                                }
                            );
                        },
                        "Reply to HR"
                    );
                },
                null
            );
            frm.change_custom_button_type("Reply to HR", null, "primary");
        }

        // Controlled Field Editability for Submitted documents (Allow on Submit override)
        if (frm.doc.docstatus === 1) {
            const leave_fields = ["leave_type", "from_date", "to_date", "half_day", "reson", "attachment"];
            const can_edit = frm.doc.workflow_state === "Clarification Requested" && frappe.user.has_role("Employee");

            // Use an interval to combat Workflow Engine property overrides
            let sync_count = 0;
            const sync_timer = setInterval(() => {
                const read_only = can_edit ? 0 : 1;
                leave_fields.forEach(f => {
                    frm.set_df_property(f, "read_only", read_only);
                    if (frm.fields_dict[f]) {
                        frm.fields_dict[f].df.read_only = read_only;
                        frm.refresh_field(f);
                    }
                });
                sync_count++;
                if (sync_count >= 5) clearInterval(sync_timer);
            }, 400);
        }

        // -------------------------------------------------
        // ALWAYS DISPLAY CONVERSATION AFTER SUBMIT
        // -------------------------------------------------
        if (frm.doc.docstatus === 1) {
            const conversation_fields = [
                "hr_query",
                "hr_query_2",
                "hr_query_3",
                "hr_query_4",
                "hr_query_5",
                "employee_reply",
                "employee_reply_2",
                "employee_reply_3",
                "employee_reply_4",
                "employee_reply_5"
            ];

            conversation_fields.forEach(f => {
                if (frm.fields_dict[f]) {
                    frm.toggle_display(f, true);
                    frm.set_df_property(f, "read_only", 1);
                    frm.refresh_field(f);
                }
            });
        }

    }
});
