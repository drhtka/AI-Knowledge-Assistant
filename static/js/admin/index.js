import {
    adminAccessModal,
    adminAccessTrigger,
} from "../dom/elements.js";

export function initializeAdminAccess() {
    if (!(adminAccessTrigger instanceof HTMLButtonElement) || !(adminAccessModal instanceof HTMLElement)) {
        return;
    }

    const openAdminAccessModal = () => {
        adminAccessModal.classList.add("is-open");
        adminAccessModal.setAttribute("aria-hidden", "false");
    };

    const closeAdminAccessModal = () => {
        adminAccessModal.classList.remove("is-open");
        adminAccessModal.setAttribute("aria-hidden", "true");
    };

    adminAccessTrigger.addEventListener("click", () => {
        openAdminAccessModal();
    });

    adminAccessModal.addEventListener("click", (event) => {
        const target = event.target instanceof HTMLElement ? event.target : null;
        if (target?.dataset.closeAdminAccessModal === "true") {
            closeAdminAccessModal();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && adminAccessModal.classList.contains("is-open")) {
            closeAdminAccessModal();
        }
    });
}
