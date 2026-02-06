frappe.views.calendar["Expense Tracker"] = {
    field_map: {
        start: "date_time",
        end: "date_time",
        id: "name",
        title: "titlenotes",
        color: "color"
    },
    get_events_method: "company.company.crm_api.get_expense_events"
};
