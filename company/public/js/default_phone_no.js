// Function to verify and setup phone field
function setup_phone_field(field, is_new) {
    // Only Phone fields
    if (!field.df || field.df.fieldtype !== "Phone") return;

    const $input = field.$input;
    if (!$input || !$input.length) return;

    // 1. 🖱️ 'Click outside' effect on mouseleave
    if (!field._mouseleave_attached) {
        $input.on('mouseleave', () => {
            // If focused and value changed, force blur to sync document
            if ($input.is(':focus') && $input.val() !== (field.get_value() || "")) {
                $input.blur();
            }
        });
        field._mouseleave_attached = true;
    }

    // 2. 🇮🇳 Default +91 logic
    // if (!is_new) return;

    // 🔒 Already initialized → never run again
    if (field._phone_ui_initialized) return;

    // 🚫 Skip if value exists (doc OR input)
    if (
        (field.get_value && field.get_value()) ||
        $input.val()
    ) {
        field._phone_ui_initialized = true;
        return;
    }

    let attempts = 0;
    const maxAttempts = 20;

    const waitForFlag = setInterval(() => {
        attempts++;

        // 🚫 User typed meanwhile → stop forever
        if ($input.val()) {
            field._phone_ui_initialized = true;
            clearInterval(waitForFlag);
            return;
        }

        const $wrapper = field.$wrapper?.find(".selected-phone");
        if (!$wrapper || !$wrapper.length) {
            if (attempts >= maxAttempts) {
                clearInterval(waitForFlag);
                // console.warn("Could not find phone field wrapper after multiple attempts.");
            }
            return;
        }

        clearInterval(waitForFlag);

        const $isd = field.$wrapper.find(".country");
        const icon = field.$wrapper.find("svg");

        // 🔁 Remove any existing flag
        $wrapper.find("img").remove();

        // 🇮🇳 India flag
        const indiaFlag = frappe.utils.flag("in");
        $wrapper.prepend(indiaFlag);

        // ☎️ +91
        if ($isd.length) $isd.text("+91");

        // 🔽 Hide dropdown arrow
        if (icon.length) icon.addClass("hide");

        // 📐 Padding adjust
        const len = $isd.text().length;
        const diff = len - 2;
        $input.css("padding-left", len > 2 ? 60 + diff * 7 : 60);

        // ✅ Mark initialized — will NEVER run again
        field._phone_ui_initialized = true;

    }, 300);
}

// 1. Standard Form View
frappe.ui.form.on('*', {
    refresh(frm) {
        setTimeout(() => {
            (frm.fields || []).forEach(field => setup_phone_field(field, frm.is_new()));
        }, 500);
    }
});

// 2. Quick Entry (Modals)
$(function () {
    $(document).on('shown.bs.modal', function () {
        if (cur_dialog && cur_dialog.fields_dict) {
            Object.values(cur_dialog.fields_dict).forEach(field => {
                // Quick Entry is always "New"
                setup_phone_field(field, true);
            });
        }
    });
});

