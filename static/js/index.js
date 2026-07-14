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

function initializeMobileNavigation() {
    const pageNav = document.getElementById("page-nav");
    const pageNavToggle = document.getElementById("page-nav-toggle");
    const pageHeaderTop = document.querySelector(".page-header-top");

    if (!(pageNav instanceof HTMLElement) || !(pageNavToggle instanceof HTMLButtonElement)) {
        return;
    }

    const mobileQuery = window.matchMedia("(max-width: 860px)");
    let isOpen = false;

    const syncState = () => {
        const isMobile = mobileQuery.matches;
        pageNav.classList.toggle("is-open", isMobile && isOpen);
        pageNavToggle.classList.toggle("is-open", isMobile && isOpen);
        pageNavToggle.setAttribute("aria-expanded", isMobile && isOpen ? "true" : "false");
        pageNavToggle.setAttribute("aria-label", isMobile && isOpen ? "Закрити навігацію" : "Відкрити навігацію");
        pageNav.setAttribute("aria-hidden", isMobile && !isOpen ? "true" : "false");
    };

    const closeMenu = () => {
        isOpen = false;
        syncState();
    };

    pageNavToggle.addEventListener("click", () => {
        if (!mobileQuery.matches) {
            return;
        }

        isOpen = !isOpen;
        syncState();
    });

    pageNav.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", closeMenu);
    });

    document.addEventListener("click", (event) => {
        if (!mobileQuery.matches || !isOpen || !(pageHeaderTop instanceof HTMLElement)) {
            return;
        }

        if (pageHeaderTop.contains(event.target instanceof Node ? event.target : null)) {
            return;
        }

        closeMenu();
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && isOpen) {
            closeMenu();
        }
    });

    mobileQuery.addEventListener("change", () => {
        if (!mobileQuery.matches) {
            isOpen = false;
        }
        syncState();
    });

    syncState();
}

demoButtons.forEach((button) => {
    button.addEventListener("click", () => {
        fillQuestionInput(button.dataset.demoQuestion ?? "");
    });
});

initializeAdminAccess();
initializeMobileNavigation();

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
