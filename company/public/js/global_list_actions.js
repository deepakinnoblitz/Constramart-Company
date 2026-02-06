/******************************************************************
 * GLOBAL LISTVIEW OVERRIDE (WORKS FOR ALL DOCTYPES)
 ******************************************************************/
const OriginalListView = frappe.views.ListView;

frappe.views.ListView = class CustomListView extends OriginalListView {

    render_list() {
        super.render_list();
        add_global_action_buttons(this); // 🔥 Always after render
        add_global_row_click_handler(this); // 🔥 Add row click navigation
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

        // Build icons
        let action_html = `
            <span class="custom-actions"
                style="margin-left:10px; display:flex; gap:20px; align-items:center; margin-right:20px;">
                ${can_edit ? `
                    <a class="edit-btn" data-name="${docname}" title="Edit" style="cursor:pointer;">
                        <svg class="icon icon-sm edit-icon" style="width:18px; height:25px; stroke: #2574b3;"><use href="#icon-edit"></use></svg>
                    </a>` : ""}
                ${can_delete ? `
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
        frappe.confirm(`Delete ${listview.doctype} ${name}?`, () => {
            frappe.call({
                method: "frappe.client.delete",
                args: { doctype: listview.doctype, name },
                callback: () => {
                    frappe.show_alert(`${listview.doctype} deleted`);
                    listview.refresh();
                }
            });
        });
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
