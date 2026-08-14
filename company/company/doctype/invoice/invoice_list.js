frappe.listview_settings['Invoice'] = {
    onload: function (listview) {
        if (listview.page.fields_dict['customer_id']) {
            listview.page.fields_dict['customer_id'].get_query = function () {
                return {
                    filters: {
                        customer_type: 'Sales'
                    }
                };
            };
        }

        // Hide default single invoice_date filter if present
        if (listview.page.fields_dict['invoice_date']) {
            listview.page.fields_dict['invoice_date'].$wrapper.hide();
        }

        // Listen to standard filter clear buttons
        listview.page.wrapper.on('click', '.btn-clear-filters, .clear-filters, .filter-x, [data-action="clear_filters"], .filter-button', function () {
            setTimeout(() => {
                let has_date_filter = listview.filter_area && listview.filter_area.get().some(f => f[1] === 'invoice_date');
                if (!has_date_filter) {
                    $('#sales_from_date_input').val('');
                    $('#sales_to_date_input').val('');
                }
            }, 100);
        });

        // Patch listview refresh to auto-clear date inputs when invoice_date filter is removed
        if (!listview._date_refresh_patched) {
            let original_refresh = listview.refresh.bind(listview);
            listview.refresh = function () {
                let has_date_filter = listview.filter_area && listview.filter_area.get().some(f => f[1] === 'invoice_date');
                if (!has_date_filter) {
                    $('#sales_from_date_input').val('');
                    $('#sales_to_date_input').val('');
                }
                return original_refresh();
            };
            listview._date_refresh_patched = true;
        }

        // Render custom From Date & To Date controls
        setTimeout(() => {
            setup_sales_date_filters(listview);
        }, 200);
    },
    get_query: function (fieldname) {
        if (fieldname === 'customer_id') {
            return {
                filters: {
                    customer_type: 'Sales'
                }
            };
        }
    }
};

function setup_sales_date_filters(listview) {
    if ($('#sales-date-filters-wrapper').length) return;

    let $filter_section = listview.page.wrapper.find('.standard-filter-section');
    if (!$filter_section.length) return;

    let $container = $(`
        <div id="sales-date-filters-wrapper" class="d-flex align-items-center" style="display: inline-flex; align-items: center; gap: 8px; margin-right: 12px;">
            <div class="frappe-control input-max-width" style="width: 145px; margin: 0;">
                <input type="text" id="sales_from_date_input" class="input-with-feedback form-control input-xs" placeholder="${__('Invoice From Date')}" readonly style="cursor: pointer;">
            </div>
            <div class="frappe-control input-max-width" style="width: 145px; margin: 0;">
                <input type="text" id="sales_to_date_input" class="input-with-feedback form-control input-xs" placeholder="${__('Invoice To Date')}" readonly style="cursor: pointer;">
            </div>
        </div>
    `);

    $filter_section.append($container);

    let $from = $container.find('#sales_from_date_input');
    let $to = $container.find('#sales_to_date_input');

    let date_format = (frappe.boot && frappe.boot.sysdefaults && frappe.boot.sysdefaults.date_format) || 'yyyy-mm-dd';

    $from.datepicker({
        language: 'en',
        autoClose: true,
        dateFormat: date_format,
        onSelect: function () {
            apply_sales_date_filter(listview);
        }
    });

    $to.datepicker({
        language: 'en',
        autoClose: true,
        dateFormat: date_format,
        onSelect: function () {
            apply_sales_date_filter(listview);
        }
    });

    $container.find('input').on('change clear input', function () {
        apply_sales_date_filter(listview);
    });
}

function apply_sales_date_filter(listview) {
    let from_val = $('#sales_from_date_input').val();
    let to_val = $('#sales_to_date_input').val();

    let from_date = from_val ? frappe.datetime.user_to_str(from_val) : null;
    let to_date = to_val ? frappe.datetime.user_to_str(to_val) : null;

    if (listview.filter_area) {
        listview.filter_area.remove('invoice_date');

        if (from_date && to_date) {
            listview.filter_area.add([['Invoice', 'invoice_date', 'between', [from_date, to_date]]]);
        } else if (from_date) {
            listview.filter_area.add([['Invoice', 'invoice_date', '>=', from_date]]);
        } else if (to_date) {
            listview.filter_area.add([['Invoice', 'invoice_date', '<=', to_date]]);
        } else {
            listview.refresh();
        }
    }
}
