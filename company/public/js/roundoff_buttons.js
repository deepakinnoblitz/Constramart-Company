// Direct rounding buttons inside Grand Total field for Invoice, Purchase, and Estimation
frappe.ui.form.on("Invoice", {
    onload(frm) { add_round_buttons(frm); },
    refresh(frm) { add_round_buttons(frm); }
});

frappe.ui.form.on("Purchase", {
    onload(frm) { add_round_buttons(frm); },
    refresh(frm) { add_round_buttons(frm); }
});

frappe.ui.form.on("Estimation", {
    onload(frm) { add_round_buttons(frm); },
    refresh(frm) { add_round_buttons(frm); }
});

function add_round_buttons(frm) {
    // Wait for form to be fully rendered
    setTimeout(() => {
        const grand_total_field = frm.fields_dict.grand_total;
        if (!grand_total_field || !grand_total_field.$wrapper) return;

        const field_wrapper = grand_total_field.$wrapper.find('.control-input-wrapper');

        // Remove existing buttons if any (e.g. on refresh)
        field_wrapper.find('.round-buttons-container').remove();

        // Style the wrapper to handle internal positioning
        field_wrapper.css({
            "position": "relative",
            "display": "flex",
            "align-items": "center"
        });

        // Create buttons container
        const buttons_html = `
            <div class="round-buttons-container" style="position: absolute; right: 8px; top: 50%; transform: translateY(-50%); display: inline-flex; gap: 4px; z-index: 10;">
                <button class="btn btn-xs btn-default round-down-btn" type="button" title="Round Down" style="padding: 2px 6px; font-size: 10px; height: 20px; min-width: 45px; border-radius: 4px; background: #fff; border: 1px solid #d1d8dd; box-shadow: 0 1px 2px rgba(0,0,0,0.05); color: #36414c; transition: all 0.2s;">
                    <svg style="width: 10px; height: 10px; stroke: currentColor; fill: none; margin-bottom: 1px;" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M19 9l-7 7-7-7" />
                    </svg>
                    <span style="font-weight: 500;">Down</span>
                </button>
                <button class="btn btn-xs btn-default round-up-btn" type="button" title="Round Up" style="padding: 2px 6px; font-size: 10px; height: 20px; min-width: 45px; border-radius: 4px; background: #fff; border: 1px solid #d1d8dd; box-shadow: 0 1px 2px rgba(0,0,0,0.05); color: #36414c; transition: all 0.2s;">
                    <svg style="width: 10px; height: 10px; stroke: currentColor; fill: none; margin-bottom: 2px;" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 15l7-7 7 7" />
                    </svg>
                    <span style="font-weight: 500;">Up</span>
                </button>
            </div>
        `;

        field_wrapper.append(buttons_html);

        // Adjust padding of the value container so it doesn't overlap with buttons
        const value_container = field_wrapper.find('.control-value');
        if (value_container.length > 0) {
            value_container.css({
                "padding-right": "110px",
                "width": "100%",
                "display": "block",
                "overflow": "hidden",
                "text-overflow": "ellipsis"
            });
        }

        // Add hover effects via JS since we are injecting style
        const btns = field_wrapper.find('.round-down-btn, .round-up-btn');
        btns.hover(
            function () { $(this).css({ "background": "#f8f9fa", "border-color": "#a8b3bc" }); },
            function () { $(this).css({ "background": "#fff", "border-color": "#d1d8dd" }); }
        );

        // Click events
        field_wrapper.find('.round-down-btn').on('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            apply_rounding(frm, "down");
        });

        field_wrapper.find('.round-up-btn').on('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            apply_rounding(frm, "up");
        });

    }, 600);
}

function apply_rounding(frm, direction) {
    // Current state values (using flt for robustness against commas/strings)
    const current_gt = flt(frm.doc.grand_total, 2);
    const current_ro = flt(frm.doc.roundoff, 2);

    // Use the unrounded natural total as baseline
    // (Total before manual rounding, but after item/tax/discount calcs)
    const natural_total = flt(current_gt - current_ro, 2);

    let target;
    if (direction === "down") {
        target = Math.floor(natural_total);
        frm._rounding_mode = 'floor';
    } else {
        target = Math.ceil(natural_total);
        frm._rounding_mode = 'ceil';
    }

    // Calculate the difference we need to add to the existing roundoff
    const diff = flt(target - natural_total, 2);
    const new_ro = flt(diff, 2); // Manual roundoff is just the diff from natural total

    // Set the hidden field
    frm.set_value('roundoff', new_ro);

    // Refresh grand total immediately in UI
    frm.set_value('grand_total', target);

    // Also update balance_amount in UI if it exists
    if (frm.fields_dict.balance_amount) {
        const paid_received = flt(frm.doc.received_amount || frm.doc.paid_amount || 0, 2);
        frm.set_value('balance_amount', flt(target - paid_received, 2));
    }

    frappe.show_alert({
        message: `Total rounded to ${frappe.format(target, { fieldtype: 'Currency' })}`,
        indicator: direction === 'down' ? 'blue' : 'green'
    }, 2);
}
