// === Standalone Unsaved Changes Navigation Guard ===

function get_active_dirty_form() {
    const cur_route = frappe.get_route ? frappe.get_route() : [];

    // Unsaved check ONLY applies when actively viewing a Form page
    if (!cur_route || cur_route.length === 0 || cur_route[0] !== 'Form') {
        return null;
    }

    const cur_frm = (window.cur_frm) || (frappe?.ui?.form?.get_cur_frm?.());
    if (!cur_frm || !cur_frm.wrapper) {
        return null;
    }

    // DO NOT intercept if form is currently saving
    if (cur_frm.is_saving || cur_frm.saving || cur_frm.in_save || cur_frm._saving || cur_frm._bypassing_unsaved_check) {
        return null;
    }

    const $wrapper = $(cur_frm.wrapper);
    if (!$wrapper.length || !$wrapper.is(':visible')) {
        return null;
    }

    // Check dirty form state (ignore if doc has just been saved)
    let is_dirty = false;
    if (cur_frm.is_dirty && cur_frm.is_dirty()) is_dirty = true;
    if (cur_frm.doc && cur_frm.doc.__unsaved) is_dirty = true;
    if ($wrapper.find('.indicator-pill:contains("Not Saved"), .indicator-pill:contains("NOT SAVED")').length > 0) is_dirty = true;

    return is_dirty ? cur_frm : null;
}

frappe.ui.form.on('*', {
    onload(frm) {
        // When opening an existing saved doc that was left dirty in memory from an abandoned session, reload clean DB version
        if (frm && frm.doc && !frm.is_new() && frm.is_dirty && frm.is_dirty() && !frm._reloaded_clean) {
            frm._reloaded_clean = true;
            frappe.model.clear_doc(frm.doctype, frm.docname);
            frm.reload_doc();
        }
    },
    before_save(frm) {
        if (frm) {
            frm._saving = true;
            frm._bypassing_unsaved_check = true;
        }
    },
    after_save(frm) {
        if (frm) {
            frm._saving = false;
            if (frm.doc) frm.doc.__unsaved = 0;
            setTimeout(() => {
                if (frm) frm._bypassing_unsaved_check = false;
            }, 1000);
        }
    }
});

// --- Intercept frappe.set_route globally when form has unsaved changes ---
if (frappe.set_route && !frappe._guard_original_set_route) {
    frappe._guard_original_set_route = frappe.set_route;
    frappe.set_route = function (...args) {
        const cur_frm = get_active_dirty_form();

        if (cur_frm) {
            // Check if route update is for the SAME doctype form (e.g. after clicking Save on a new doc)
            if (args && args.length >= 2 && args[0] === 'Form' && args[1] === cur_frm.doctype) {
                return frappe._guard_original_set_route.apply(frappe, args);
            }

            frappe.confirm(
                __('You have unsaved changes. Are you sure you want to leave without saving?'),
                function () {
                    if (cur_frm.doc && !cur_frm.is_new()) {
                        cur_frm.doc.__unsaved = 0;
                        frappe.model.clear_doc(cur_frm.doctype, cur_frm.docname);
                    }
                    cur_frm._bypassing_unsaved_check = true;
                    window.cur_frm = null;

                    frappe._guard_original_set_route.apply(frappe, args).then(() => {
                        setTimeout(() => { if (cur_frm) cur_frm._bypassing_unsaved_check = false; }, 500);
                    });
                }
            );
            return Promise.reject('Navigation cancelled due to unsaved changes');
        }

        return frappe._guard_original_set_route.apply(frappe, args);
    };
}

// --- Global Capture-Phase Interceptor for Navigation Links & Sidebar ---
document.addEventListener('click', function (e) {
    if (!e.target) return;

    // 1. Check if an active, visible Form is dirty
    const cur_frm = get_active_dirty_form();
    if (!cur_frm) return;

    const $target = $(e.target);

    // 2. Allow interactions INSIDE active form wrapper or active dialogs/dropdowns/datepickers
    if (cur_frm.wrapper && $.contains(cur_frm.wrapper[0], e.target)) {
        if ($target.closest('.btn-back-global').length === 0) {
            return;
        }
    }

    if ($target.closest('.modal-dialog, .flatpickr-calendar, .ui-autocomplete, .dropdown-menu, .popover, .select2-container, .desk-search').length) {
        return;
    }

    // 3. Click OUTSIDE the active form -> BLOCK navigation immediately and prompt for confirmation!
    e.preventDefault();
    e.stopImmediatePropagation();
    e.stopPropagation();

    frappe.confirm(
        __('You have unsaved changes. Are you sure you want to leave without saving?'),
        function () {
            if (cur_frm.doc && !cur_frm.is_new()) {
                cur_frm.doc.__unsaved = 0;
                frappe.model.clear_doc(cur_frm.doctype, cur_frm.docname);
            }
            cur_frm._bypassing_unsaved_check = true;
            window.cur_frm = null;

            const nav_el = e.target.closest('a, [href], [data-route], .sidebar-item-container, .standard-sidebar-item, .item-anchor, .navbar-brand, .breadcrumb');
            let href = null;
            let data_route = null;
            if (nav_el) {
                href = nav_el.getAttribute('href') || (nav_el.querySelector('a[href]') && nav_el.querySelector('a[href]').getAttribute('href'));
                data_route = nav_el.getAttribute('data-route');
            }

            if (data_route) {
                frappe.set_route(data_route);
            } else if (href && href !== '#' && href !== 'javascript:void(0);') {
                if (href.startsWith('/app/')) {
                    const route_parts = href.replace('/app/', '').split('?')[0].split('/');
                    frappe.set_route(route_parts);
                } else {
                    window.location.href = href;
                }
            } else {
                setTimeout(() => {
                    e.target.click();
                }, 50);
            }

            setTimeout(() => { if (cur_frm) cur_frm._bypassing_unsaved_check = false; }, 800);
        },
        function () {
            return false;
        }
    );

    return false;
}, true);
