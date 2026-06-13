const questionForm = document.getElementById("question-form");
const clearFormButton = document.getElementById("clear-form");
const demoButtons = document.querySelectorAll("[data-demo-question]");
const uploadForm = document.getElementById("upload-form");
const uploadResult = document.getElementById("upload-result");

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

if (uploadForm instanceof HTMLFormElement && uploadResult instanceof HTMLElement) {
    uploadForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const fileInput = uploadForm.elements.namedItem("file");
        if (!(fileInput instanceof HTMLInputElement) || !fileInput.files || fileInput.files.length === 0) {
            uploadResult.className = "upload-result error-text";
            uploadResult.textContent = "Choose a .txt or .md file first.";
            return;
        }

        const formData = new FormData();
        formData.append("file", fileInput.files[0]);

        uploadResult.className = "upload-result meta";
        uploadResult.textContent = "Uploading document and rebuilding chunks...";

        try {
            const response = await fetch("/ingest", {
                method: "POST",
                body: formData,
            });
            const payload = await response.json();

            if (!response.ok) {
                const errorMessage = payload.detail ?? "Upload failed.";
                uploadResult.className = "upload-result error-text";
                uploadResult.textContent = errorMessage;
                return;
            }

            uploadResult.className = "upload-result success-text";
            uploadResult.textContent =
                `Uploaded ${payload.filename}. Loaded chunks: ${payload.chunks_loaded}.`;
            uploadForm.reset();
        } catch {
            uploadResult.className = "upload-result error-text";
            uploadResult.textContent = "Upload failed because the server did not respond.";
        }
    });
}
