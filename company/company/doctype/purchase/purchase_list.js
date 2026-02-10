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
