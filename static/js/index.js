const questionForm = document.getElementById("question-form");
const clearFormButton = document.getElementById("clear-form");
const demoButtons = document.querySelectorAll("[data-demo-question]");
const uploadForm = document.getElementById("upload-form");
const uploadResult = document.getElementById("upload-result");
const chunkingPresetForm = document.getElementById("chunking-preset-form");
const chunkingResult = document.getElementById("chunking-result");

function renderUploadStatus(message, className = "upload-result meta") {
    if (!(uploadResult instanceof HTMLElement)) {
        return;
    }

    uploadResult.className = className;
    uploadResult.textContent = message;
}

function renderUploadSuccess(payload) {
    if (!(uploadResult instanceof HTMLElement)) {
        return;
    }

    uploadResult.className = "upload-result upload-result-card success-text";
    uploadResult.replaceChildren();

    const title = document.createElement("strong");
    title.textContent = "Document uploaded successfully";

    const details = document.createElement("p");
    details.className = "meta";
    details.textContent =
        `file=${payload.source_name} | type=${payload.file_type} | chunks=${payload.chunks_loaded}`;

    const followUp = document.createElement("p");
    followUp.className = "meta";
    followUp.textContent = "The document is now part of the local retrieval index.";

    const ctaButton = document.createElement("button");
    ctaButton.type = "button";
    ctaButton.textContent = "Ask About This Document";
    ctaButton.addEventListener("click", () => {
        if (!(questionForm instanceof HTMLFormElement)) {
            return;
        }

        const questionInput = questionForm.elements.namedItem("question");
        if (questionInput instanceof HTMLInputElement) {
            questionInput.value = `What is ${payload.source_name} about?`;
            questionInput.focus();
            questionInput.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    });

    uploadResult.append(title, details, followUp, ctaButton);
}

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
            uploadResult.textContent = "Choose a .txt, .md, or .pdf file first.";
            return;
        }

        const formData = new FormData();
        formData.append("file", fileInput.files[0]);

        renderUploadStatus("Uploading document and rebuilding chunks...");

        try {
            const response = await fetch("/ingest", {
                method: "POST",
                body: formData,
            });
            const payload = await response.json();

            if (!response.ok) {
                const errorMessage = payload.detail ?? "Upload failed.";
                renderUploadStatus(errorMessage, "upload-result error-text");
                return;
            }

            renderUploadSuccess(payload);
            uploadForm.reset();
        } catch {
            renderUploadStatus(
                "Upload failed because the server did not respond.",
                "upload-result error-text",
            );
        }
    });
}

if (chunkingPresetForm instanceof HTMLFormElement && chunkingResult instanceof HTMLElement) {
    chunkingPresetForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const presetInput = chunkingPresetForm.elements.namedItem("chunking_preset");
        if (!(presetInput instanceof HTMLSelectElement)) {
            return;
        }

        chunkingResult.className = "upload-result meta";
        chunkingResult.textContent = "Applying chunking preset and rebuilding chunks...";

        try {
            const response = await fetch("/chunking-config", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ preset: presetInput.value }),
            });
            const payload = await response.json();

            if (!response.ok) {
                const errorMessage = payload.detail ?? "Chunking preset update failed.";
                chunkingResult.className = "upload-result error-text";
                chunkingResult.textContent = errorMessage;
                return;
            }

            chunkingResult.className = "upload-result success-text";
            chunkingResult.textContent =
                `Applied ${payload.current_preset}: chunk_size=${payload.chunk_size_words}, overlap=${payload.chunk_overlap_words}.`;
            window.location.reload();
        } catch {
            chunkingResult.className = "upload-result error-text";
            chunkingResult.textContent = "Preset update failed because the server did not respond.";
        }
    });
}
