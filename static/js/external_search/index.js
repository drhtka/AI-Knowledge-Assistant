import {
    externalSearchClearButton,
    externalSearchInput,
} from "../dom/elements.js";

export function initializeExternalSearchPage() {
    if (!(externalSearchInput instanceof HTMLTextAreaElement) || !(externalSearchClearButton instanceof HTMLButtonElement)) {
        return;
    }

    const syncExternalSearchClearButton = () => {
        const hasValue = externalSearchInput.value.trim().length > 0;
        externalSearchClearButton.classList.toggle("is-active", hasValue && !externalSearchInput.disabled);
        externalSearchClearButton.disabled = !hasValue || externalSearchInput.disabled;
    };

    externalSearchInput.addEventListener("input", () => {
        syncExternalSearchClearButton();
    });

    externalSearchClearButton.addEventListener("click", () => {
        if (externalSearchClearButton.disabled) {
            return;
        }
        externalSearchInput.value = "";
        syncExternalSearchClearButton();
        externalSearchInput.focus();
    });

    syncExternalSearchClearButton();
}
