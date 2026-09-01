// === Universal "Back" Button (Instant Fast Render) ===

function add_global_back_button(frm) {
    if (!frm || !frm.page || !frm.page.wrapper) return;

    const $wrapper = frm.page.wrapper;
    const $pageActions = $wrapper.find('.page-actions');
    if (!$pageActions.length) return;

    // Prevent duplicates
    if ($pageActions.find('.btn-back-global').length) return;

    // Create Back button
    const backBtn = $(`
        <button class="btn btn-outline-secondary btn-sm btn-back-global" title="Go Back" style="margin-right: 8px; background-color: #f8f8f8 !important; border: 1px solid rgba(30, 47, 64, 0.3) !important; color: #1E293B !important; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);">
            ← Back
        </button>
    `);

    // Click action
    backBtn.on('click', function() {
        let is_dirty = false;
        if (frm.is_dirty && frm.is_dirty()) is_dirty = true;
        if (frm.doc && (frm.doc.__unsaved || frm.doc.__islocal)) is_dirty = true;
        if ($('.indicator-pill:contains("Not Saved"), .indicator-pill:contains("NOT SAVED")').length > 0) is_dirty = true;

        if (is_dirty) {
            frappe.confirm(
                __('You have unsaved changes. Are you sure you want to leave without saving?'),
                function() {
                    // User confirmed: clear unsaved in-memory draft for existing saved doc
                    if (frm.doc && !frm.is_new()) {
                        frm.doc.__unsaved = 0;
                        frappe.model.clear_doc(frm.doctype, frm.docname);
                    }
                    frm._bypassing_unsaved_check = true;
                    window.cur_frm = null;
                    if (window.history.length > 1) {
                        window.history.back();
                    } else if (frm.doctype) {
                        frappe.set_route('List', frm.doctype);
                    }
                    setTimeout(() => { frm._bypassing_unsaved_check = false; }, 500);
                }
            );
        } else {
            if (window.history.length > 1) {
                window.history.back();
            } else if (frm.doctype) {
                frappe.set_route('List', frm.doctype);
            }
        }
    });

    // Insert immediately at the start of page-actions or before Print button
    const $printBtn = $pageActions.find('.btn-print, .menu-btn-group .btn[data-original-title="Print"]');
    if ($printBtn.length) {
        $printBtn.closest('div').prepend(backBtn);
    } else {
        $pageActions.prepend(backBtn);
    }

    // Handle Quick Entry or Link dialogs
    if (frm.$wrapper && frm.$wrapper.closest('.modal-dialog').length) {
        const modalFooter = frm.$wrapper.closest('.modal-dialog').find('.modal-footer');
        if (!modalFooter.find('.btn-back-dialog').length) {
            const backDialog = $(`<button class="btn btn-secondary btn-back-dialog">← Back</button>`)
                .css({ marginRight: '8px' })
                .on('click', function() {
                    frm.$wrapper.closest('.modal-dialog').find('.btn-modal-close').trigger('click');
                });
            modalFooter.prepend(backDialog);
        }
    }
}

// --- Apply globally to all doctypes INSTANTLY ---
frappe.ui.form.on('*', {
    refresh(frm) {
        add_global_back_button(frm);
    },
    onload_post_render(frm) {
        add_global_back_button(frm);
    }
});

// Fast observer fallback in case page-actions renders asynchronously
$(document).on('page-change', () => {
    const cur_frm = frappe?.ui?.form?.get_cur_frm?.();
    if (cur_frm) add_global_back_button(cur_frm);
});
