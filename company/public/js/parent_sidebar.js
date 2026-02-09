document.addEventListener(
    "click",
    function (e) {
        if (!e.target) return;
        const parentItem = e.target.closest(".sidebar-item-container");
        if (!parentItem) return;

        const childContainer = parentItem.querySelector(":scope > .sidebar-child-item");
        const hasChildren = childContainer && childContainer.children.length > 0;

        // If NO children → allow routing (CRM Dashboard, Lead List, etc.)
        if (!hasChildren) return;

        const clickedHeader = e.target.closest(".standard-sidebar-item");
        if (!clickedHeader) return;

        // BLOCK routing ONLY for parents
        e.preventDefault();
        e.stopImmediatePropagation();

        // AUTO-CLOSE OTHER OPEN MODULES
        closeOtherModules(parentItem);

        // SMOOTH TOGGLE
        toggleAccordion(childContainer);

        // Toggle arrow icon
        const arrow = parentItem.querySelector(".drop-icon use");
        if (arrow) {
            const now = arrow.getAttribute("href");
            arrow.setAttribute(
                "href",
                now.includes("down") ? "#es-line-up" : "#es-line-down"
            );
        }
    },
    true
);

// ---- SMOOTH ANIMATION ----
function toggleAccordion(el) {
    if (el.classList.contains("hidden")) {
        el.classList.remove("hidden");
        el.style.maxHeight = el.scrollHeight + "px";
        setTimeout(() => (el.style.maxHeight = "none"), 300);
    } else {
        el.style.maxHeight = el.scrollHeight + "px";
        setTimeout(() => {
            el.style.maxHeight = "0px";
        }, 10);
        setTimeout(() => el.classList.add("hidden"), 300);
    }
}

// ---- AUTO-CLOSE OTHERS ----
function closeOtherModules(current) {
    // Only query for OPEN child items to avoid iterating over everything
    const openChildren = document.querySelectorAll(".sidebar-child-item:not(.hidden)");

    openChildren.forEach(child => {
        const container = child.closest(".sidebar-item-container");

        // Skip if it's the current one we just clicked
        if (container === current) return;

        // Close it
        child.style.maxHeight = child.scrollHeight + "px";
        setTimeout(() => {
            child.style.maxHeight = "0px";
        }, 10);
        setTimeout(() => child.classList.add("hidden"), 300);

        // Reset arrow icon
        if (container) {
            const arrow = container.querySelector(".drop-icon use");
            if (arrow) arrow.setAttribute("href", "#es-line-down");
        }
    });
}
