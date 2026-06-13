const questionForm = document.getElementById("question-form");
const clearFormButton = document.getElementById("clear-form");
const demoButtons = document.querySelectorAll("[data-demo-question]");

demoButtons.forEach((button) => {
    button.addEventListener("click", () => {
        if (!questionForm) {
            return;
        }

        const questionInput = questionForm.elements.namedItem("question");
        if (questionInput instanceof HTMLInputElement) {
            questionInput.value = button.dataset.demoQuestion ?? "";
        }
    });
});

if (clearFormButton && questionForm) {
    clearFormButton.addEventListener("click", () => {
        const questionInput = questionForm.elements.namedItem("question");
        const topKInput = questionForm.elements.namedItem("top_k");
        const retrievalModeInput = questionForm.elements.namedItem("retrieval_mode");

        if (questionInput instanceof HTMLInputElement) {
            questionInput.value = "";
        }

        if (topKInput instanceof HTMLInputElement) {
            topKInput.value = "3";
        }

        if (retrievalModeInput instanceof HTMLSelectElement) {
            retrievalModeInput.value = "auto";
        }
    });
}
