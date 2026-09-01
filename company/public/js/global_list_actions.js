/******************************************************************
 * GLOBAL LISTVIEW OVERRIDE (WORKS FOR ALL DOCTYPES)
 ******************************************************************/
const OriginalListView = frappe.views.ListView;

frappe.views.ListView = class CustomListView extends OriginalListView {
    setup_view() {
        if (super.setup_view) super.setup_view();

        // Register instance-specific listener for auto-refresh
        // This ensures the current list refreshes whenever a document of its type is saved
        frappe.ui.form.on(this.doctype, {
            after_save: () => {
                console.log(`[Auto-Refresh] Document saved for ${this.doctype}. Refreshing List...`);
                this.refresh();
            }
        });

        // Add realtime listener for server-side updates
        // We listen to both 'list_update' (custom) and 'doc_update' (standard)
        frappe.realtime.on("list_update", (data) => {
            if (data && data.doctype === this.doctype) {
                console.log(`[Realtime-Refresh] List update detected for ${this.doctype}. Refreshing...`);
                this.refresh();
            }
        });

        frappe.realtime.on("doc_update", (data) => {
            if (data && data.doctype === this.doctype) {
                console.log(`[Realtime-Refresh] Document update detected for ${this.doctype}. Refreshing...`);
                this.refresh();
            }
        });
    }

    render_list() {
        super.render_list();
        add_global_action_buttons(this); //  Always after render
        add_global_row_click_handler(this); //  Add row click navigation
    }

    refresh() {
        super.refresh();
        add_global_action_buttons(this); // optional safety
        add_global_row_click_handler(this); // optional safety
    }
};


/******************************************************************
 * INLINE CSS (Injected only once globally)
 ******************************************************************/
(function inject_global_css() {
    if (document.getElementById("global_list_css")) return;

    const css = `
        .custom-actions .delete-icon {
            color: #e03131 !important;
        }
        .custom-actions .edit-icon {
            color: #495057 !important;
        }
        .custom-actions a:hover svg {
            color: #1c7ed6 !important;
        }
    `;

    let styleTag = document.createElement("style");
    styleTag.id = "global_list_css";
    styleTag.innerHTML = css;
    document.head.appendChild(styleTag);
})();


/******************************************************************
 * MAIN GLOBAL ACTION BUTTON FUNCTION (NO DUPLICATES)
 ******************************************************************/
function add_global_action_buttons(listview) {

    const can_edit = frappe.model.can_write(listview.doctype);
    const can_delete = frappe.model.can_delete(listview.doctype);

    if (!can_edit && !can_delete) return;

    // For Collection doctypes, fetch the real DB latest collection for each party
    if (listview.doctype === "Invoice Collection" || listview.doctype === "Purchase Collection") {
        const is_invoice = listview.doctype === "Invoice Collection";
        const party_field = is_invoice ? "customer_id" : "vendor_id";
        
        let party_set = new Set();
        (listview.data || []).forEach(d => {
            const party = d[party_field] || d[is_invoice ? "customer_name" : "vendor_name"] || d[is_invoice ? "customer" : "vendor"];
            if (party) party_set.add(party);
        });

        const parties = Array.from(party_set);
        if (!parties.length) {
            render_all_rows(listview, can_edit, can_delete, null);
            return;
        }

        frappe.db.get_list(listview.doctype, {
            filters: [[party_field, "in", parties]],
            fields: ["name", party_field, "creation"],
            order_by: "creation desc",
            limit_page_length: 500
        }).then(records => {
            let latest_db_map = {}; // party -> latest_docname
            (records || []).forEach(r => {
                const party = r[party_field];
                if (party && !latest_db_map[party]) {
                    latest_db_map[party] = r.name;
                }
            });
            render_all_rows(listview, can_edit, can_delete, latest_db_map);
        });

        return;
    }

    render_all_rows(listview, can_edit, can_delete, null);
}

function render_all_rows(listview, can_edit, can_delete, latest_db_map) {
    // Loop through each row container
    listview.$result.find(".list-row-container").each(function () {

        let row_container = $(this);

        // 🚨 HARD FIX: If icons already added once, DO NOT add again
        if (row_container.hasClass("actions-added")) return;
        row_container.addClass("actions-added");

        // Identify row
        let row = row_container.find(".list-row");
        if (!row.length) row = row_container;

        let docname =
            row.attr("data-name") ||
            row.find(".list-row-check").attr("data-name") ||
            row.find("[data-name]").attr("data-name");

        if (!docname) return;

        // Right-side action section
        let right_section = row.find(".level-right");
        if (!right_section.length) return;

        // Determine if this row is editable/deletable
        let allow_edit = can_edit;
        let allow_delete = can_delete;

        if (latest_db_map && (listview.doctype === "Invoice Collection" || listview.doctype === "Purchase Collection")) {
            const is_invoice = listview.doctype === "Invoice Collection";
            const party_field = is_invoice ? "customer_id" : "vendor_id";
            const doc_item = (listview.data || []).find(d => d.name === docname);
            if (doc_item) {
                const party = doc_item[party_field] || doc_item[is_invoice ? "customer_name" : "vendor_name"] || doc_item[is_invoice ? "customer" : "vendor"];
                if (party && latest_db_map[party] && latest_db_map[party] !== docname) {
                    allow_edit = false;
                    allow_delete = false;
                }
            }
        }

        if (!allow_edit && !allow_delete) return;

        // Build icons
        let action_html = `
            <span class="custom-actions"
                style="margin-left:10px; display:flex; gap:20px; align-items:center; margin-right:20px;">
                ${allow_edit ? `
                    <a class="edit-btn" data-name="${docname}" title="Edit" style="cursor:pointer;">
                        <svg class="icon icon-sm edit-icon" style="width:18px; height:25px; stroke: #2574b3;"><use href="#icon-edit"></use></svg>
                    </a>` : ""}
                ${allow_delete ? `
                    <a class="delete-btn" data-name="${docname}" title="Delete" style="cursor:pointer;">
                        <svg class="icon icon-sm delete-icon" style="width:18px; height:25px; stroke: #ff0000;"><use href="#icon-delete"></use></svg>
                    </a>` : ""}
            </span>`;

        // Add the icons ONCE
        right_section.append(action_html);

    });

    // EDIT
    listview.$result.off("click", ".edit-btn");
    listview.$result.on("click", ".edit-btn", function (e) {
        e.stopPropagation();
        frappe.set_route("Form", listview.doctype, $(this).data("name"));
    });

    // DELETE
    listview.$result.off("click", ".delete-btn");
    listview.$result.on("click", ".delete-btn", function (e) {
        e.stopPropagation();

        let name = $(this).data("name");
        let $row = $(this).closest(".list-row-container"); // Capture row for instant removal

        function do_standard_delete() {
            frappe.confirm(`Delete ${listview.doctype} ${name}?`, () => {
                frappe.call({
                    method: "frappe.client.delete",
                    args: { doctype: listview.doctype, name },
                    callback: (r) => {
                        if (!r.exc) {
                            frappe.show_alert(`${listview.doctype} deleted`);
                            $row.fadeOut(300, function () { $(this).remove(); });
                            if (listview.data) {
                                listview.data = listview.data.filter(d => d.name !== name);
                            }
                            frappe.model.remove_from_locals(listview.doctype, name);
                            listview.refresh();
                        }
                    }
                });
            });
        }

        if (listview.doctype === "Invoice" || listview.doctype === "Purchase") {
            frappe.call({
                method: "company.company.api.check_mutual_invoice_purchase_connection",
                args: { doctype: listview.doctype, name: name },
                callback: (r) => {
                    if (r.message && r.message.mutually_connected) {
                        const linked_doc = r.message.linked_doc;
                        const linked_dt = r.message.linked_doctype;

                        const inv_name = listview.doctype === "Invoice" ? name : linked_doc;
                        const pur_name = listview.doctype === "Purchase" ? name : linked_doc;

                        frappe.confirm(
                            __("{0} <b>{1}</b> and {2} <b>{3}</b> are connected together.<br><br>Do you want to delete <b>BOTH</b> {0} and {2}?", [listview.doctype, name, linked_dt, linked_doc]),
                            () => {
                                frappe.call({
                                    method: "company.company.api.delete_linked_invoice_and_purchase",
                                    args: { invoice: inv_name, purchase: pur_name },
                                    freeze: true,
                                    freeze_message: __("Deleting connected Invoice & Purchase..."),
                                    callback: (res) => {
                                        if (!res.exc) {
                                            frappe.show_alert({message: __("Invoice and Purchase deleted successfully"), indicator: "green"});
                                            $row.fadeOut(300, function () { $(this).remove(); });
                                            if (listview.data) {
                                                listview.data = listview.data.filter(d => d.name !== name && d.name !== linked_doc);
                                            }
                                            frappe.model.remove_from_locals(listview.doctype, name);
                                            frappe.model.remove_from_locals(linked_dt, linked_doc);
                                            listview.refresh();
                                        }
                                    }
                                });
                            }
                        );
                    } else {
                        do_standard_delete();
                    }
                }
            });
        } else {
            do_standard_delete();
        }
    });
}


/******************************************************************
 * GLOBAL ROW CLICK HANDLER (NAVIGATE TO EDIT PAGE)
 ******************************************************************/
function add_global_row_click_handler(listview) {

    // Remove any existing click handlers to avoid duplicates
    listview.$result.off('click', '.list-row');

    // Add click handler to all list rows
    listview.$result.on('click', '.list-row', function (e) {
        const $target = $(e.target);

        // Don't navigate if clicking on:
        // - Checkbox
        // - Custom action buttons (edit/delete icons)
        // - Like button
        // - Any input or button elements
        if (
            $target.closest('.list-row-checkbox').length ||
            $target.closest('.list-row-check').length ||
            $target.closest('.custom-actions').length ||
            $target.closest('.edit-btn').length ||
            $target.closest('.delete-btn').length ||
            $target.closest('.like-action').length ||
            $target.closest('.list-row-like').length ||
            $target.is('input') ||
            $target.is('button') ||
            $target.closest('button').length
        ) {
            return; // Let the default action happen
        }

        // Get the document name from the row
        const $row = $(this);
        const docName =
            $row.attr('data-name') ||
            $row.find('.list-row-checkbox').data('name') ||
            $row.find('.list-row-check').data('name') ||
            $row.find('[data-name]').first().data('name');

        if (docName && listview.doctype) {
            // Navigate to the form view (edit page)
            frappe.set_route('Form', listview.doctype, docName);
        }
    });
}
