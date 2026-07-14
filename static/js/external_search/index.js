import {
    externalSearchClearButton,
    externalSearchInput,
    externalSearchSubmitButton,
} from "../dom/elements.js";

export function initializeExternalSearchPage() {
    if (!(externalSearchInput instanceof HTMLTextAreaElement) || !(externalSearchClearButton instanceof HTMLButtonElement)) {
        return;
    }

    const isInputLocked = externalSearchInput.disabled;

    const syncExternalSearchClearButton = () => {
        const hasValue = externalSearchInput.value.trim().length > 0;
        externalSearchClearButton.classList.toggle("is-active", hasValue && !isInputLocked);
        externalSearchClearButton.disabled = !hasValue || isInputLocked;
        if (externalSearchSubmitButton instanceof HTMLButtonElement) {
            externalSearchSubmitButton.disabled = !hasValue || isInputLocked;
        }
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
