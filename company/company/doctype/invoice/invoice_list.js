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

        // Patch listview refresh to sync date inputs with active filter_area and restore checked state
        if (!listview._date_refresh_patched) {
            let original_refresh = listview.refresh.bind(listview);
            listview.refresh = function () {
                sync_sales_date_inputs(listview);
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
            setup_sales_date_filters(listview);
        }, 200);

        // Add Export Invoice Details button under Actions menu
        listview.page.add_inner_button(__('Export Invoice Details'), function () {
            let current_checked = listview.get_checked_items().map(item => item.name);
            let combined_set = new Set(listview._selected_names || []);
            current_checked.forEach(n => combined_set.add(n));
            let selected_names = Array.from(combined_set);

            let filters = {};

            // 1. Extract custom date inputs
            if ($('#sales_from_date_input').val()) {
                filters.from_date = frappe.datetime.user_to_str($('#sales_from_date_input').val());
            }
            if ($('#sales_to_date_input').val()) {
                filters.to_date = frappe.datetime.user_to_str($('#sales_to_date_input').val());
            }

            // 2. Extract page fields_dict values
            if (listview.page && listview.page.fields_dict) {
                Object.keys(listview.page.fields_dict).forEach(fname => {
                    let field = listview.page.fields_dict[fname];
                    if (field && field.get_value && field.get_value()) {
                        filters[fname] = field.get_value();
                    }
                });
            }

            // 3. Extract Filter Area filters
            if (listview.filter_area && listview.filter_area.get) {
                let flist = listview.filter_area.get();
                (flist || []).forEach(f => {
                    if (Array.isArray(f) && f.length >= 4) {
                        let fname = f[1];
                        let fval = f[3];
                        if (fname && fval) {
                            filters[fname] = fval;
                        }
                    }
                });
            }

            // 4. Extract URL query parameters fallback
            let url_params = frappe.utils.get_query_params();
            Object.keys(url_params).forEach(k => {
                if (k && url_params[k] && !filters[k]) {
                    filters[k] = url_params[k];
                }
            });

            frappe.call({
                method: 'company.company.api.get_sales_export_count',
                args: {
                    filters: JSON.stringify(filters),
                    names: JSON.stringify(selected_names)
                },
                callback: function (r) {
                    let counts = r.message || { invoice_count: 0, item_count: 0 };
                    let inv_count = counts.invoice_count || 0;
                    let item_count = counts.item_count || 0;

                    if (inv_count === 0) {
                        frappe.msgprint({
                            title: __('No Invoices Found'),
                            message: __('There are no invoices matching the selected filters to export.'),
                            indicator: 'orange'
                        });
                        return;
                    }

                    frappe.confirm(
                        __('Are you sure you want to download <b>{0} Invoice(s)</b> to Excel?', [inv_count]),
                        function () {
                            frappe.dom.freeze(__('Generating Excel Report, please wait...'));

                            fetch('/api/method/company.company.api.export_sales_itemized_excel', {
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
                                frappe.dom.unfreeze();
                                let url = window.URL.createObjectURL(blob);
                                let a = document.createElement('a');
                                a.href = url;
                                a.download = 'Sales_Item_Details_Report.xlsx';
                                document.body.appendChild(a);
                                a.click();
                                a.remove();
                                window.URL.revokeObjectURL(url);
                                frappe.show_alert({ message: __('Excel Report downloaded successfully!'), indicator: 'green' });
                            })
                            .catch(err => {
                                frappe.dom.unfreeze();
                                frappe.msgprint(__('Failed to generate Excel report. Please try again.'));
                            });
                        }
                    );
                }
            });
        });
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
    if ($('#sales_from_date_input').length) return;

    let $filter_section = listview.page.wrapper.find('.standard-filter-section');
    if (!$filter_section.length) return;

    let $from_wrap = $(`
        <div class="form-group frappe-control input-max-width" style="margin-bottom: 0;">
            <input type="text" id="sales_from_date_input" class="input-with-feedback form-control input-xs" placeholder="${__('Invoice From Date')}" readonly style="cursor: pointer;">
        </div>
    `);

    let $to_wrap = $(`
        <div class="form-group frappe-control input-max-width" style="margin-bottom: 0;">
            <input type="text" id="sales_to_date_input" class="input-with-feedback form-control input-xs" placeholder="${__('Invoice To Date')}" readonly style="cursor: pointer;">
        </div>
    `);

    $filter_section.append($from_wrap).append($to_wrap);

    let $from = $from_wrap.find('#sales_from_date_input');
    let $to = $to_wrap.find('#sales_to_date_input');

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

    $from_wrap.add($to_wrap).find('input').on('change clear input', function () {
        apply_sales_date_filter(listview);
    });

    sync_sales_date_inputs(listview);
}

function sync_sales_date_inputs(listview) {
    if (!listview || !listview.filter_area) return;
    let $from = $('#sales_from_date_input');
    let $to = $('#sales_to_date_input');
    if (!$from.length || !$to.length) return;

    let filters = listview.filter_area.get();
    let date_filter = filters.find(f => f[1] === 'invoice_date');

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
