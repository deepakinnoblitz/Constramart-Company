// frappe.listview_settings["Meeting"] = {
//     add_fields: ["from", "to"],

//     onload(listview) {
//         frappe.after_ajax(() => {
//             const route = frappe.get_route();
//             if (route[0] === "List" && route[1] === "Meeting" && route[3] !== "Calendar") {
//                 frappe.set_route("List", "Meeting", "Calendar");
//             }
//         });
//     },
// };
