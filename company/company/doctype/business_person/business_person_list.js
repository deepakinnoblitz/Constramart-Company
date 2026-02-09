frappe.listview_settings['Business Person'] = {
    onload: function (listview) {
        // Listen for save events from Quick Entry or other forms to refresh the list
        frappe.ui.form.on('Business Person', {
            after_save: function (frm) {
                if (listview) {
                    listview.refresh();
                }
            }
        });
    }
};
