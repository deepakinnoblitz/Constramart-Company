frappe.listview_settings['Purchase'] = {
    onload: function (listview) {
        if (listview.page.fields_dict['vendor_id']) {
            listview.page.fields_dict['vendor_id'].get_query = function () {
                return {
                    filters: {
                        customer_type: 'Purchase'
                    }
                };
            };
        }

        // Hide default single bill_date filter if present
        if (listview.page.fields_dict['bill_date']) {
            listview.page.fields_dict['bill_date'].$wrapper.hide();
        }

        // Listen to standard filter clear buttons
        listview.page.wrapper.on('click', '.btn-clear-filters, .clear-filters, .filter-x, [data-action="clear_filters"], .filter-button', function () {
            setTimeout(() => {
                let has_date_filter = listview.filter_area && listview.filter_area.get().some(f => f[1] === 'bill_date');
                if (!has_date_filter) {
                    $('#purchase_from_date_input').val('');
                    $('#purchase_to_date_input').val('');
                }
            }, 100);
        });

        // Setup multi-page checkbox selection persistence
        if (!listview._selection_tracker_setup) {
            listview._selected_names = new Set();

            listview.$page.on('change', '.list-row-checkbox', function () {
                let name = $(this).attr('data-name');
                if (!name) {
                    name = $(this).closest('.list-row-container, .list-row').attr('data-name');
                }
                if (name) {
                    if (this.checked) {
                        listview._selected_names.add(name);
                    } else {
                        listview._selected_names.delete(name);
                    }
                }
            });

            listview.$page.on('change', '.list-check-all', function () {
                let is_checked = this.checked;
                listview.$page.find('.list-row-checkbox').each(function () {
                    let name = $(this).attr('data-name') || $(this).closest('.list-row-container, .list-row').attr('data-name');
                    if (name) {
                        if (is_checked) {
                            listview._selected_names.add(name);
                        } else {
                            listview._selected_names.delete(name);
                        }
                    }
                });
            });

            listview._selection_tracker_setup = true;
        }

        // Patch listview refresh to auto-clear date inputs when bill_date filter is removed and restore checked state
        if (!listview._date_refresh_patched) {
            let original_refresh = listview.refresh.bind(listview);
            listview.refresh = function () {
                let has_date_filter = listview.filter_area && listview.filter_area.get().some(f => f[1] === 'bill_date');
                if (!has_date_filter) {
                    $('#purchase_from_date_input').val('');
                    $('#purchase_to_date_input').val('');
                }
                let p = original_refresh();
                setTimeout(() => {
                    if (listview._selected_names && listview._selected_names.size) {
                        listview.$page.find('.list-row-checkbox').each(function () {
                            let name = $(this).attr('data-name') || $(this).closest('.list-row-container, .list-row').attr('data-name');
                            if (name && listview._selected_names.has(name)) {
                                $(this).prop('checked', true);
                            }
                        });
                    }
                }, 300);
                return p;
            };
            listview._date_refresh_patched = true;
        }

        // Render custom From Date & To Date controls
        setTimeout(() => {
            setup_purchase_date_filters(listview);
        }, 200);

        // Add Export Purchase Details button under Actions menu
        listview.page.add_inner_button(__('Export Purchase Details'), function () {
            let current_checked = listview.get_checked_items().map(item => item.name);
            let combined_set = new Set(listview._selected_names || []);
            current_checked.forEach(n => combined_set.add(n));
            let selected_names = Array.from(combined_set);

            let from_date = $('#purchase_from_date_input').val() ? frappe.datetime.user_to_str($('#purchase_from_date_input').val()) : null;
            let to_date = $('#purchase_to_date_input').val() ? frappe.datetime.user_to_str($('#purchase_to_date_input').val()) : null;
            let vendor_id = listview.page.fields_dict['vendor_id'] ? listview.page.fields_dict['vendor_id'].get_value() : null;

            let filters = {
                from_date: from_date,
                to_date: to_date,
                vendor_id: vendor_id
            };

            frappe.call({
                method: 'company.company.api.get_purchase_export_count',
                args: {
                    filters: JSON.stringify(filters),
                    names: JSON.stringify(selected_names)
                },
                callback: function (r) {
                    let counts = r.message || { purchase_count: 0, item_count: 0 };
                    let pur_count = counts.purchase_count || 0;
                    let item_count = counts.item_count || 0;

                    if (pur_count === 0) {
                        frappe.msgprint({
                            title: __('No Purchases Found'),
                            message: __('There are no purchases matching the selected filters to export.'),
                            indicator: 'orange'
                        });
                        return;
                    }

                    frappe.confirm(
                        __('Are you sure you want to download <b>{0} Purchase(s)</b> to Excel?', [pur_count]),
                        function () {
                            frappe.freeze(__('Generating Excel Report, please wait...'));

                            fetch('/api/method/company.company.api.export_purchase_itemized_excel', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/x-www-form-urlencoded',
                                    'X-Frappe-CSRF-Token': frappe.csrf_token
                                },
                                body: $.param({
                                    filters: JSON.stringify(filters),
                                    names: JSON.stringify(selected_names)
                                })
                            })
                            .then(response => response.blob())
                            .then(blob => {
                                frappe.unfreeze();
                                let url = window.URL.createObjectURL(blob);
                                let a = document.createElement('a');
                                a.href = url;
                                a.download = 'Purchase_Item_Details_Report.xlsx';
                                document.body.appendChild(a);
                                a.click();
                                a.remove();
                                window.URL.revokeObjectURL(url);
                                frappe.show_alert({ message: __('Excel Report downloaded successfully!'), indicator: 'green' });
                            })
                            .catch(err => {
                                frappe.unfreeze();
                                frappe.msgprint(__('Failed to generate Excel report. Please try again.'));
                            });
                        }
                    );
                }
            });
        });
    },
    get_query: function (fieldname) {
        if (fieldname === 'vendor_id') {
            return {
                filters: {
                    customer_type: 'Purchase'
                }
            };
        }
    }
};

function setup_purchase_date_filters(listview) {
    if ($('#purchase_from_date_input').length) return;

    let $filter_section = listview.page.wrapper.find('.standard-filter-section');
    if (!$filter_section.length) return;

    let $from_wrap = $(`
        <div class="form-group frappe-control input-max-width" style="margin-bottom: 0;">
            <input type="text" id="purchase_from_date_input" class="input-with-feedback form-control input-xs" placeholder="${__('Bill From Date')}" readonly style="cursor: pointer;">
        </div>
    `);

    let $to_wrap = $(`
        <div class="form-group frappe-control input-max-width" style="margin-bottom: 0;">
            <input type="text" id="purchase_to_date_input" class="input-with-feedback form-control input-xs" placeholder="${__('Bill To Date')}" readonly style="cursor: pointer;">
        </div>
    `);

    $filter_section.append($from_wrap).append($to_wrap);

    let $from = $from_wrap.find('#purchase_from_date_input');
    let $to = $to_wrap.find('#purchase_to_date_input');

    let date_format = (frappe.boot && frappe.boot.sysdefaults && frappe.boot.sysdefaults.date_format) || 'yyyy-mm-dd';

    $from.datepicker({
        language: 'en',
        autoClose: true,
        dateFormat: date_format,
        onSelect: function () {
            apply_purchase_date_filter(listview);
        }
    });

    $to.datepicker({
        language: 'en',
        autoClose: true,
        dateFormat: date_format,
        onSelect: function () {
            apply_purchase_date_filter(listview);
        }
    });

    $from_wrap.add($to_wrap).find('input').on('change clear input', function () {
        apply_purchase_date_filter(listview);
    });
}

function apply_purchase_date_filter(listview) {
    let from_val = $('#purchase_from_date_input').val();
    let to_val = $('#purchase_to_date_input').val();

    let from_date = from_val ? frappe.datetime.user_to_str(from_val) : null;
    let to_date = to_val ? frappe.datetime.user_to_str(to_val) : null;

    if (listview.filter_area) {
        listview.filter_area.remove('bill_date');

        if (from_date && to_date) {
            listview.filter_area.add([['Purchase', 'bill_date', 'between', [from_date, to_date]]]);
        } else if (from_date) {
            listview.filter_area.add([['Purchase', 'bill_date', '>=', from_date]]);
        } else if (to_date) {
            listview.filter_area.add([['Purchase', 'bill_date', '<=', to_date]]);
        } else {
            listview.refresh();
        }
    }
}
