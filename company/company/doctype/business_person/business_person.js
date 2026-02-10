// Copyright (c) 2026, deepak and contributors
// For license information, please see license.txt

frappe.ui.form.on("Business Person", {


    refresh(frm) {
        // 🚀 SILENCE: Hide the hard error dialog container
        if (!$('#silence-bp-dialog').length) {
            $('<style id="silence-bp-dialog">#dialog-container { display: none !important; }</style>').appendTo('head');
        }
    },
    
    after_save(frm) {
        show_custom_bp_toast(__("Saved Successfully"), "green");
    }
});



/**
 * Custom toast notification for Business Person DocType
 * Bypasses the hidden #alert-container/dialog-container
 */
function show_custom_bp_toast(msg, type) {
    const is_green = type === "green";
    const bg = is_green ? "#e2f6ec" : "#fff5e6";
    const color = is_green ? "#28a745" : "#ffc107";
    const border = is_green ? "#ade3c8" : "#ffe5cc";
    const icon = is_green ? "fa-check-circle" : "fa-exclamation-triangle";

    const toast = $(`
        <div class="custom-bp-toast" style="
            position: fixed;
            bottom: 40px;
            right: 40px;
            padding: 14px 24px;
            background: ${bg};
            color: ${color};
            border: 1px solid ${border};
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            z-index: 100001;
            font-size: 14px;
            display: none;
            align-items: center;
            gap: 10px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        ">
            <i class="fa ${icon}" style="font-size: 16px;"></i>
            <span>${msg}</span>
        </div>
    `).appendTo('body');

    toast.css('display', 'flex').hide().fadeIn(300).delay(2500).fadeOut(500, function () {
        $(this).remove();
    });
}
