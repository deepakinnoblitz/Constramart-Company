frappe.listview_settings["Lead"] = {
    onload(listview) {

        setTimeout(() => {
            const $actions = $(".standard-actions");

            if (!$actions.length) return;

            // Prevent duplicates
            if ($actions.find(".btn-import-lead").length) return;

            // Exact Same Style As Add Lead
            let import_btn = $(`
                <button class="btn btn-primary btn-sm primary-action btn-import-lead" 
                        data-label="Import" 
                        style="margin-right: 8px;">
                    <svg class="icon icon-xs" aria-hidden="true">
                        <use href="#icon-upload"></use>
                    </svg>
                    <span class="hidden-xs">Import</span>
                </button>
            `);

            // Route to Data Import
            import_btn.on("click", () => {
                frappe.set_route("data-import", {
                    reference_doctype: "Lead"
                });
            });

            // Insert before Add Lead button
            $actions.find("button.primary-action").first().before(import_btn);

        }, 500);
    }
};
