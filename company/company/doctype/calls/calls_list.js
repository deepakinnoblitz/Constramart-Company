// frappe.listview_settings["Calls"] = {
//     add_fields: ["call_start_time", "call_end_time"],

//     onload(listview) {
//         frappe.after_ajax(() => {
//             const route = frappe.get_route();
//             if (route[0] === "List" && route[1] === "Calls" && route[3] !== "Calendar") {
//                 frappe.set_route("List", "Calls", "Calendar");
//             }
//         });
//     },
// };
