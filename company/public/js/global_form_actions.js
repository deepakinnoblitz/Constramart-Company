/**
 * GLOBAL FORM ACTIONS
 * - Add Rename Icon next to record title in Form Header
 */

frappe.ui.form.on("*", {
    refresh: function (frm) {
        // 1. Check if renaming is allowed and user has write permission
        // toolbar.js logic: this.frm.perm[0].write && this.frm.meta.allow_rename && !this.frm.doc.__islocal
        if (frm.meta && frm.meta.allow_rename && !frm.is_new() && frm.perm[0] && frm.perm[0].write) {

            // 2. Find the title text element in the page header
            const title_area = frm.page.$title_area.find(".title-text");

            if (title_area.length) {
                // 3. Prevent duplicate icons
                if (title_area.find(".custom-rename-icon").length === 0) {
                    const $icon = $(`
                        <a class="custom-rename-icon" title="Rename Document" style="
                            margin-left: 12px; 
                            cursor: pointer; 
                            display: inline-flex; 
                            vertical-align: middle;
                            transition: transform 0.2s ease;
                        ">
                            <svg class="icon icon-sm" style="width: 16px; height: 16px; stroke: #2574b3; fill: none;"><use href="#icon-edit"></use></svg>
                        </a>
                    `);

                    // 4. Trigger the Rename Dialog on click
                    $icon.on("click", (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        
                        // Use standard Frappe rename method
                        frappe.model.rename_doc(frm.doctype, frm.docname);
                    });

                    // 5. Add hover effect
                    $icon.hover(
                        function() { $(this).css('transform', 'scale(1.1)'); },
                        function() { $(this).css('transform', 'scale(1.0)'); }
                    );

                    title_area.append($icon);
                }
            }
        }
    }
});
