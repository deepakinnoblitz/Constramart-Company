frappe.ui.form.on("Lead", {
    refresh(frm) {
        render_sales_pipeline(frm);
    }
});

function render_sales_pipeline(frm) {
    const fieldname = "sales_pipeline";
    const field = frm.get_field(fieldname);
    if (!field) return;

    const $wrapper = field.$wrapper;

    // Prevent duplicate render
    if ($wrapper.find(".sales-pipeline-container").length) return;

    // Hide textarea
    $wrapper.find("textarea").hide();

    const stages = [
        { key: "Prospecting", color: "#2563eb" },
        { key: "Qualifying", color: "#f97316" },
        { key: "Engaging", color: "#0ea5e9" },
        { key: "Proposal", color: "#a855f7" },
        { key: "Closing", color: "#22c55e" },
        { key: "Retaining", color: "#16a34a" }
    ];

    const html = `
        <div class="sales-pipeline-container">
            <div class="pipeline-track">
                ${stages.map((s, i) => `
                    <div class="pipeline-stage"
                         data-stage="${s.key}"
                         data-index="${i}"
                         style="--stage-color:${s.color}">
                        <span>${s.key}</span>
                    </div>
                `).join("")}
            </div>
        </div>
    `;

    $wrapper.append(html);

    // Click handler
    $wrapper.find(".pipeline-stage").on("click", function () {
        const stage = $(this).data("stage");
        frm.set_value(fieldname, stage);
        update_pipeline_ui($wrapper, stages, stage);
    });

    // Initial state
    update_pipeline_ui($wrapper, stages, frm.doc[fieldname]);
}

function update_pipeline_ui($wrapper, stages, activeStage) {
    let activeIndex = stages.findIndex(s => s.key === activeStage);

    $wrapper.find(".pipeline-stage").each(function () {
        const index = parseInt($(this).data("index"));

        $(this).removeClass("active completed");

        if (index < activeIndex) {
            $(this).addClass("completed");
        } else if (index === activeIndex) {
            $(this).addClass("active");
        }
    });
}
