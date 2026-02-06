frappe.listview_settings['Purchase Collection'] = {
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
