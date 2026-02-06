let forcing_calendar = false;

frappe.router.on("change", () => {
    if (forcing_calendar) return;  // prevent loop during routing

    const route = frappe.get_route();
    const FORCE = ["Calls", "Meeting", "Event", "ToDo"];

    // route must be complete: ["List", "Calls", "Calendar"]
    if (!route || route.length < 2) return;

    if (route[0] === "List" && FORCE.includes(route[1])) {

        // If already in Calendar → do nothing
        if (route[2] === "Calendar" || route[3] === "Calendar") {
            return;
        }

        // SAFE REDIRECT
        forcing_calendar = true;
        frappe.set_route("List", route[1], "Calendar");

        // allow router to run again later
        setTimeout(() => forcing_calendar = false, 300);
    }
});
