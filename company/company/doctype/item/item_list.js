frappe.listview_settings['Item'] = {
    onload: function (listview) {
        // Listen for save events from Quick Entry or other forms to refresh the list
        frappe.ui.form.on('Item', {
            after_save: function (frm) {
                if (listview) {
                    listview.refresh();
                }
            }
        });
    }
};
