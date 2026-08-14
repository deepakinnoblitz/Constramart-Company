frappe.listview_settings['Purchase Collection'] = {
    onload: function (listview) {
        if (listview.page.fields_dict['payment_date']) {
            listview.page.fields_dict['payment_date'].$wrapper.hide();
        }

        // Listen to standard filter clear buttons
        listview.page.wrapper.on('click', '.btn-clear-filters, .clear-filters, .filter-x, [data-action="clear_filters"], .filter-button', function () {
            setTimeout(() => {
                let has_date_filter = listview.filter_area && listview.filter_area.get().some(f => f[1] === 'payment_date');
                if (!has_date_filter) {
                    $('#purchase_coll_from_date_input').val('');
                    $('#purchase_coll_to_date_input').val('');
                }
            }, 100);
        });

        // Patch listview refresh to auto-clear date inputs when payment_date filter is removed
        if (!listview._date_refresh_patched) {
            let original_refresh = listview.refresh.bind(listview);
            listview.refresh = function () {
                let has_date_filter = listview.filter_area && listview.filter_area.get().some(f => f[1] === 'payment_date');
                if (!has_date_filter) {
                    $('#purchase_coll_from_date_input').val('');
                    $('#purchase_coll_to_date_input').val('');
                }
                return original_refresh();
            };
            listview._date_refresh_patched = true;
        }

        // Render custom From Date & To Date controls
        setTimeout(() => {
            setup_purchase_collection_date_filters(listview);
        }, 200);
    },
    refresh(listview) {
        if (!listview || !listview.data) return;

        listview.data.forEach(doc => {
            if (!doc.purchase || !doc.name) return;

            // Check if there are newer collections for the same purchase order
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Purchase Collection",
                    filters: {
                        purchase: doc.purchase,
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

                        // Run multiple times to catch late renders
                        hide_actions();
                        setTimeout(hide_actions, 200);
                        setTimeout(hide_actions, 1500);
                    }
                }
            });
        });
    }
};

function setup_purchase_collection_date_filters(listview) {
    if ($('#purchase-collection-date-filters-wrapper').length) return;

    let $filter_section = listview.page.wrapper.find('.standard-filter-section');
    if (!$filter_section.length) return;

    let $container = $(`
        <div id="purchase-collection-date-filters-wrapper" class="d-flex align-items-center" style="display: inline-flex; align-items: center; gap: 8px; margin-right: 12px;">
            <div class="frappe-control input-max-width" style="width: 145px; margin: 0;">
                <input type="text" id="purchase_coll_from_date_input" class="input-with-feedback form-control input-xs" placeholder="${__('Payment From Date')}" readonly style="cursor: pointer;">
            </div>
            <div class="frappe-control input-max-width" style="width: 145px; margin: 0;">
                <input type="text" id="purchase_coll_to_date_input" class="input-with-feedback form-control input-xs" placeholder="${__('Payment To Date')}" readonly style="cursor: pointer;">
            </div>
        </div>
    `);

    $filter_section.append($container);

    let $from = $container.find('#purchase_coll_from_date_input');
    let $to = $container.find('#purchase_coll_to_date_input');

    let date_format = (frappe.boot && frappe.boot.sysdefaults && frappe.boot.sysdefaults.date_format) || 'yyyy-mm-dd';

    $from.datepicker({
        language: 'en',
        autoClose: true,
        dateFormat: date_format,
        onSelect: function () {
            apply_purchase_collection_date_filter(listview);
        }
    });

    $to.datepicker({
        language: 'en',
        autoClose: true,
        dateFormat: date_format,
        onSelect: function () {
            apply_purchase_collection_date_filter(listview);
        }
    });

    $container.find('input').on('change clear input', function () {
        apply_purchase_collection_date_filter(listview);
    });
}

function apply_purchase_collection_date_filter(listview) {
    let from_val = $('#purchase_coll_from_date_input').val();
    let to_val = $('#purchase_coll_to_date_input').val();

    let from_date = from_val ? frappe.datetime.user_to_str(from_val) : null;
    let to_date = to_val ? frappe.datetime.user_to_str(to_val) : null;

    if (listview.filter_area) {
        listview.filter_area.remove('payment_date');

        if (from_date && to_date) {
            listview.filter_area.add([['Purchase Collection', 'payment_date', 'between', [from_date, to_date]]]);
        } else if (from_date) {
            listview.filter_area.add([['Purchase Collection', 'payment_date', '>=', from_date]]);
        } else if (to_date) {
            listview.filter_area.add([['Purchase Collection', 'payment_date', '<=', to_date]]);
        } else {
            listview.refresh();
        }
    }
}
