frappe.listview_settings['Invoice Collection'] = {
    onload: function (listview) {
        if (listview.page.fields_dict['collection_date']) {
            listview.page.fields_dict['collection_date'].$wrapper.hide();
        }

        // Listen to standard filter clear buttons
        listview.page.wrapper.on('click', '.btn-clear-filters, .clear-filters, .filter-x, [data-action="clear_filters"], .filter-button', function () {
            setTimeout(() => {
                let has_date_filter = listview.filter_area && listview.filter_area.get().some(f => f[1] === 'collection_date');
                if (!has_date_filter) {
                    $('#sales_coll_from_date_input').val('');
                    $('#sales_coll_to_date_input').val('');
                }
            }, 100);
        });

        // Patch listview refresh to sync date inputs with active filter_area
        if (!listview._date_refresh_patched) {
            let original_refresh = listview.refresh.bind(listview);
            listview.refresh = function () {
                sync_sales_collection_date_inputs(listview);
                return original_refresh();
            };
            listview._date_refresh_patched = true;
        }

        // Render custom From Date & To Date controls
        setTimeout(() => {
            setup_sales_collection_date_filters(listview);
        }, 200);
    },
    refresh(listview) {
        if (!listview || !listview.data) return;

        listview.data.forEach(doc => {
            if (!doc.invoice || !doc.name) return;

            // Check if there are newer collections for the same invoice
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Invoice Collection",
                    filters: {
                        invoice: doc.invoice,
                        creation: [">", doc.creation],
                        name: ["!=", doc.name]
                    },
                    limit: 1
                },
                callback: function (r) {
                    if (r && r.message && r.message.length > 0) {
                        // This is NOT the latest collection. 

                        const hide_actions = () => {
                            // Find any element related to this record to locate the row
                            const $targets = $('[data-name="' + doc.name + '"]');

                            $targets.each(function () {
                                const $row = $(this).closest('.list-row, .list-row-container');
                                if ($row.length) {
                                    // 1. Forcefully hide the custom actions container and buttons
                                    // Using cssText to allow !important which overrides inline styles
                                    $row.find(".custom-actions, .edit-btn, .delete-btn, .list-row-actions")
                                        .css("cssText", "display: none !important;");
                                }
                            });
                        };

                        // Run twice: immediately and after a short delay to ensure we catch Frappe's post-render logic
                        hide_actions();
                        setTimeout(hide_actions, 200);
                        setTimeout(hide_actions, 1500);
                    }
                }
            });
        });
    }
};

function setup_sales_collection_date_filters(listview) {
    if ($('#sales_coll_from_date_input').length) return;

    let $filter_section = listview.page.wrapper.find('.standard-filter-section');
    if (!$filter_section.length) return;

    let $from_wrap = $(`
        <div class="form-group frappe-control input-max-width" style="margin-bottom: 0;">
            <input type="text" id="sales_coll_from_date_input" class="input-with-feedback form-control input-xs" placeholder="${__('Collection From Date')}" readonly style="cursor: pointer;">
        </div>
    `);

    let $to_wrap = $(`
        <div class="form-group frappe-control input-max-width" style="margin-bottom: 0;">
            <input type="text" id="sales_coll_to_date_input" class="input-with-feedback form-control input-xs" placeholder="${__('Collection To Date')}" readonly style="cursor: pointer;">
        </div>
    `);

    $filter_section.append($from_wrap).append($to_wrap);

    let $from = $from_wrap.find('#sales_coll_from_date_input');
    let $to = $to_wrap.find('#sales_coll_to_date_input');

    let date_format = (frappe.boot && frappe.boot.sysdefaults && frappe.boot.sysdefaults.date_format) || 'yyyy-mm-dd';

    $from.datepicker({
        language: 'en',
        autoClose: true,
        dateFormat: date_format,
        onSelect: function () {
            apply_sales_collection_date_filter(listview);
        }
    });

    $to.datepicker({
        language: 'en',
        autoClose: true,
        dateFormat: date_format,
        onSelect: function () {
            apply_sales_collection_date_filter(listview);
        }
    });

    $from_wrap.add($to_wrap).find('input').on('change clear input', function () {
        apply_sales_collection_date_filter(listview);
    });

    sync_sales_collection_date_inputs(listview);
}

function sync_sales_collection_date_inputs(listview) {
    if (!listview || !listview.filter_area) return;
    let $from = $('#sales_coll_from_date_input');
    let $to = $('#sales_coll_to_date_input');
    if (!$from.length || !$to.length) return;

    let filters = listview.filter_area.get();
    let date_filter = filters.find(f => f[1] === 'collection_date');

    if (date_filter) {
        let op = date_filter[2];
        let val = date_filter[3];

        let from_str = null;
        let to_str = null;

        if (Array.isArray(val)) {
            from_str = val[0];
            to_str = val[1];
        } else if (op === '>=' || op === '>') {
            from_str = val;
        } else if (op === '<=' || op === '<') {
            to_str = val;
        } else if (op === '=') {
            from_str = val;
            to_str = val;
        }

        if (from_str) {
            let formatted_from = frappe.datetime.str_to_user(from_str);
            if ($from.val() !== formatted_from) $from.val(formatted_from);
        }
        if (to_str) {
            let formatted_to = frappe.datetime.str_to_user(to_str);
            if ($to.val() !== formatted_to) $to.val(formatted_to);
        }
    } else {
        if ($from.val() !== '') $from.val('');
        if ($to.val() !== '') $to.val('');
    }
}

function apply_sales_collection_date_filter(listview) {
    let from_val = $('#sales_coll_from_date_input').val();
    let to_val = $('#sales_coll_to_date_input').val();

    let from_date = from_val ? frappe.datetime.user_to_str(from_val) : null;
    let to_date = to_val ? frappe.datetime.user_to_str(to_val) : null;

    if (listview.filter_area) {
        listview.filter_area.remove('collection_date');

        if (from_date && to_date) {
            listview.filter_area.add([['Invoice Collection', 'collection_date', 'between', [from_date, to_date]]]);
        } else if (from_date) {
            listview.filter_area.add([['Invoice Collection', 'collection_date', '>=', from_date]]);
        } else if (to_date) {
            listview.filter_area.add([['Invoice Collection', 'collection_date', '<=', to_date]]);
        } else {
            listview.refresh();
        }
    }
}
