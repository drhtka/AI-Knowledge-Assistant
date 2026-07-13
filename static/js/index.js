import {
    clearFormButton,
    demoButtons,
    questionForm,
} from "./dom/elements.js";
import {
    clearQuestionInputAndState,
    fillQuestionInput,
    getNormalizedQuestionValue,
    getQuestionClearButton,
    getQuestionInput,
    resetQuestionResultState,
    replaceUrlWithoutQuestionParams,
    submitQuestionWithFetch,
    syncQuestionActionState,
} from "./ask/index.js";
import { initializeUploadPage } from "./upload/index.js";
import { initializeAdminAccess } from "./admin/index.js";
import { initializeExternalSearchPage } from "./external_search/index.js";
import { initializeAllCustomSelects } from "./custom_selects/index.js";
import {
    initializeChunkingControls,
    initializeStorageBackendControls,
} from "./system/config.js";
import { initializeReindexControls } from "./system/reindex.js";

demoButtons.forEach((button) => {
    button.addEventListener("click", () => {
        fillQuestionInput(button.dataset.demoQuestion ?? "");
    });
});

initializeAdminAccess();

if (questionForm instanceof HTMLFormElement) {
    const questionInput = getQuestionInput();
    const questionClearControl = getQuestionClearButton();

    syncQuestionActionState();

    if (
        (questionInput instanceof HTMLInputElement || questionInput instanceof HTMLTextAreaElement) &&
        !questionInput.readOnly
    ) {
        questionInput.addEventListener("input", () => {
            syncQuestionActionState();
        });
    }

    if (questionClearControl instanceof HTMLButtonElement) {
        questionClearControl.addEventListener("click", () => {
            if (questionClearControl.disabled) {
                return;
            }
            clearQuestionInputAndState();
        });
    }

    questionForm.addEventListener("submit", (event) => {
        const questionValue = getNormalizedQuestionValue();

        if (!questionValue) {
            event.preventDefault();
            replaceUrlWithoutQuestionParams();
            resetQuestionResultState();

            if (questionInput instanceof HTMLInputElement || questionInput instanceof HTMLTextAreaElement) {
                questionInput.focus();
            }
            return;
        }

        if (questionInput instanceof HTMLInputElement || questionInput instanceof HTMLTextAreaElement) {
            questionInput.value = questionValue;
        }
        if (typeof window.fetch === "function") {
            event.preventDefault();
            void submitQuestionWithFetch(questionValue);
        }
    });
}

if (clearFormButton && questionForm && !getQuestionClearButton()) {
    clearFormButton.addEventListener("click", () => {
        clearQuestionInputAndState();
    });
}

initializeUploadPage();
initializeChunkingControls();
initializeExternalSearchPage();
initializeAllCustomSelects();
initializeStorageBackendControls();
initializeReindexControls();
