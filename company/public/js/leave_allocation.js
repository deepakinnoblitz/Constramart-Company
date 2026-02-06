frappe.listview_settings['Leave Allocation'] = {
    onload: function(listview) {
        // Add custom button
        listview.page.add_inner_button(__('Auto Allocate Monthly Leaves'), function() {
            frappe.prompt(
                [
                    {
                        fieldname: 'year',
                        label: 'Year',
                        fieldtype: 'Int',
                        default: frappe.datetime.now_date().split("-")[0], // current year
                        reqd: 1
                    },
                    {
                        fieldname: 'month',
                        label: 'Month',
                        fieldtype: 'Int',
                        default: parseInt(frappe.datetime.now_date().split("-")[1]), // current month
                        reqd: 1
                    }
                ],
                function(values){
                    frappe.call({
                        method: "company.company.api.auto_allocate_monthly_leaves",
                        args: {
                            year: values.year,
                            month: values.month
                        },
                        callback: function(r){
                            if(r.message){
                                frappe.msgprint(r.message);
                                listview.refresh();  // reload list
                            }
                        }
                    });
                },
                __('Select Year and Month'),
                __('Allocate')
            );
        });
    }
};
