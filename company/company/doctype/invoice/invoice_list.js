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
        if (listview.page.fields_dict['invoice_date']) {
            listview.page.fields_dict['invoice_date'].$input.on('input', function () {
                if (!$(this).val()) {
                    listview.refresh();
                }
            });
        }
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
