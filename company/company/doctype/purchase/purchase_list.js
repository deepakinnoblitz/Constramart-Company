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
        if (listview.page.fields_dict['bill_date']) {
            listview.page.fields_dict['bill_date'].$input.on('input', function () {
                if (!$(this).val()) {
                    listview.refresh();
                }
            });
        }
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
