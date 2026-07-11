const questionForm = document.getElementById("question-form");
const clearFormButton = document.getElementById("clear-form");
const demoButtons = document.querySelectorAll("[data-demo-question]");
const uploadForm = document.getElementById("upload-form");
const uploadResult = document.getElementById("upload-result");
const chunkingPresetForm = document.getElementById("chunking-preset-form");
const chunkingResult = document.getElementById("chunking-result");
const storageBackendForm = document.getElementById("storage-backend-form");
const storageBackendResult = document.getElementById("storage-backend-result");
const reindexStatusBadge = document.getElementById("reindex-status-badge");
const reindexTrigger = document.getElementById("reindex-trigger");
const reindexRerunRequested = document.getElementById("reindex-rerun-requested");
const reindexDocumentCount = document.getElementById("reindex-document-count");
const reindexChunkCount = document.getElementById("reindex-chunk-count");
const reindexElapsedMs = document.getElementById("reindex-elapsed-ms");
const reindexStartedAt = document.getElementById("reindex-started-at");
const reindexFinishedAt = document.getElementById("reindex-finished-at");
const reindexStatusMessage = document.getElementById("reindex-status-message");
const refreshReindexStatusButton = document.getElementById("refresh-reindex-status-button");
const startReindexButton = document.getElementById("start-reindex-button");

function fillQuestionInput(questionText) {
    if (!(questionForm instanceof HTMLFormElement)) {
        const nextUrl = new URL(window.location.origin + "/");
        nextUrl.searchParams.set("question", questionText);
        window.location.assign(nextUrl.toString());
        return;
    }

    const questionInput = questionForm.elements.namedItem("question");
    if (questionInput instanceof HTMLInputElement) {
        questionInput.value = questionText;
        questionInput.focus();
        questionInput.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
    }

    const nextUrl = new URL(window.location.origin + "/");
    nextUrl.searchParams.set("question", questionText);
    window.location.assign(nextUrl.toString());
}

function renderUploadStatus(message, className = "upload-result meta") {
    if (!(uploadResult instanceof HTMLElement)) {
        return;
    }

    uploadResult.className = className;
    uploadResult.textContent = message;
}

function updateReindexBadge(state) {
    if (!(reindexStatusBadge instanceof HTMLElement)) {
        return;
    }

    reindexStatusBadge.textContent = state;
    reindexStatusBadge.className = `dashboard-badge reindex-badge reindex-badge-${state}`;
}

function renderReindexStatus(payload) {
    if (!(reindexStatusBadge instanceof HTMLElement)) {
        return;
    }

    updateReindexBadge(payload.state ?? "idle");

    if (reindexTrigger instanceof HTMLElement) {
        reindexTrigger.textContent = payload.trigger || "unknown";
    }
    if (reindexRerunRequested instanceof HTMLElement) {
        reindexRerunRequested.textContent = payload.rerun_requested ? "yes" : "no";
    }
    if (reindexDocumentCount instanceof HTMLElement) {
        reindexDocumentCount.textContent = String(payload.document_count ?? 0);
    }
    if (reindexChunkCount instanceof HTMLElement) {
        reindexChunkCount.textContent = String(payload.chunk_count ?? 0);
    }
    if (reindexElapsedMs instanceof HTMLElement) {
        reindexElapsedMs.textContent = String(payload.elapsed_ms ?? 0);
    }
    if (reindexStartedAt instanceof HTMLElement) {
        reindexStartedAt.textContent = payload.started_at || "not started yet";
    }
    if (reindexFinishedAt instanceof HTMLElement) {
        reindexFinishedAt.textContent = payload.finished_at || "not finished yet";
    }
    if (reindexStatusMessage instanceof HTMLElement) {
        reindexStatusMessage.classList.toggle("reindex-status-error", Boolean(payload.last_error));
        if (payload.last_error) {
            reindexStatusMessage.textContent = `last_error=${payload.last_error}`;
        } else if (payload.rerun_requested && payload.rerun_trigger) {
            reindexStatusMessage.textContent =
                `rerun_trigger=${payload.rerun_trigger} | started_at=${payload.started_at || "pending"}`;
        } else if (payload.started_at) {
            reindexStatusMessage.textContent = `started_at=${payload.started_at}`;
        } else {
            reindexStatusMessage.textContent = "Waiting for the next reindex trigger.";
        }
    }
}

function renderReindexMessage(message, isError = false) {
    if (!(reindexStatusMessage instanceof HTMLElement)) {
        return;
    }

    reindexStatusMessage.textContent = message;
    reindexStatusMessage.classList.toggle("reindex-status-error", isError);
}

async function refreshReindexStatus() {
    if (!(reindexStatusBadge instanceof HTMLElement)) {
        return;
    }

    try {
        const response = await fetch("/reindex-status");
        if (!response.ok) {
            return;
        }
        const payload = await response.json();
        renderReindexStatus(payload);
    } catch {
        // Keep the last known status visible if polling fails.
    }
}

async function startReindexFromUi() {
    if (!(startReindexButton instanceof HTMLButtonElement)) {
        return;
    }

    startReindexButton.disabled = true;
    renderReindexMessage("Starting background reindex...");

    try {
        const response = await fetch("/reindex", { method: "POST" });
        const payload = await response.json();

        if (!response.ok) {
            const errorMessage = payload.detail ?? "Failed to start reindex.";
            renderReindexMessage(errorMessage, true);
            return;
        }

        renderReindexMessage(payload.message || "Background reindex request accepted.");
        await refreshReindexStatus();
    } catch {
        renderReindexMessage("Failed to start reindex because the server did not respond.", true);
    } finally {
        startReindexButton.disabled = false;
    }
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
        `file=${payload.source_name} | type=${payload.file_type} | estimated_chunks=${payload.estimated_chunks}`;

    const followUp = document.createElement("p");
    followUp.className = "meta";
    followUp.textContent = payload.reindex_message || "Background reindex status updated.";

    let previewBlock = null;
    if (typeof payload.preview_text === "string" && payload.preview_text.trim()) {
        previewBlock = document.createElement("div");
        previewBlock.className = "upload-preview";

        const previewTitle = document.createElement("p");
        previewTitle.className = "meta";
        const previewTitleStrong = document.createElement("strong");
        previewTitleStrong.textContent = "Document Preview";
        previewTitle.append(previewTitleStrong);

        const previewText = document.createElement("p");
        previewText.className = "upload-preview-text";
        previewText.textContent = payload.preview_text;

        previewBlock.append(previewTitle, previewText);
    }

    const ctaButton = document.createElement("button");
    ctaButton.type = "button";
    ctaButton.textContent = "Ask About This Document";
    ctaButton.addEventListener("click", () => {
        fillQuestionInput(`What is ${payload.source_name} about?`);
    });

    const quickPromptIntro = document.createElement("p");
    quickPromptIntro.className = "meta";
    quickPromptIntro.textContent = "Quick prompts for the uploaded document:";

    const quickPromptActions = document.createElement("div");
    quickPromptActions.className = "actions";

    const quickPrompts = [
        `What is ${payload.source_name} about?`,
        `What are the key points in ${payload.source_name}?`,
        `Summarize ${payload.source_name} in simple terms.`,
    ];

    quickPrompts.forEach((promptText) => {
        const promptButton = document.createElement("button");
        promptButton.type = "button";
        promptButton.textContent = promptText;
        promptButton.addEventListener("click", () => {
            fillQuestionInput(promptText);
        });
        quickPromptActions.append(promptButton);
    });

    if (previewBlock instanceof HTMLDivElement) {
        uploadResult.append(title, details, followUp, previewBlock, ctaButton, quickPromptIntro, quickPromptActions);
        return;
    }

    uploadResult.append(title, details, followUp, ctaButton, quickPromptIntro, quickPromptActions);
}

demoButtons.forEach((button) => {
    button.addEventListener("click", () => {
        fillQuestionInput(button.dataset.demoQuestion ?? "");
    });
});

if (clearFormButton && questionForm) {
    clearFormButton.addEventListener("click", () => {
        const nextUrl = new URL(window.location.href);
        nextUrl.searchParams.delete("question");
        nextUrl.searchParams.delete("top_k");
        nextUrl.searchParams.delete("retrieval_mode");
        nextUrl.searchParams.delete("web_question");
        nextUrl.searchParams.delete("web_top_k");
        window.location.assign(nextUrl.pathname + nextUrl.search);
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

        renderUploadStatus("Uploading document and scheduling background reindex...");

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
            void refreshReindexStatus();
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
    const presetInput = chunkingPresetForm.elements.namedItem("chunking_preset");

    chunkingPresetForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (!(presetInput instanceof HTMLSelectElement)) {
            return;
        }

        presetInput.disabled = true;

        chunkingResult.className = "upload-result meta";
        chunkingResult.textContent = "Applying chunking preset and scheduling background reindex...";

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
                `Preset updated: ${payload.chunk_size_words}/${payload.chunk_overlap_words}. ${payload.reindex_message}`;
            void refreshReindexStatus();
            window.setTimeout(() => {
                window.location.reload();
            }, 2200);
        } catch {
            chunkingResult.className = "upload-result error-text";
            chunkingResult.textContent = "Preset update failed because the server did not respond.";
        } finally {
            if (presetInput instanceof HTMLSelectElement) {
                presetInput.disabled = false;
            }
        }
    });

    if (presetInput instanceof HTMLSelectElement) {
        presetInput.addEventListener("change", () => {
            chunkingPresetForm.requestSubmit();
        });
    }
}

if (storageBackendForm instanceof HTMLFormElement && storageBackendResult instanceof HTMLElement) {
    storageBackendForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const backendInput = storageBackendForm.elements.namedItem("storage_backend");
        if (!(backendInput instanceof HTMLSelectElement)) {
            return;
        }

        storageBackendResult.className = "upload-result meta";
        storageBackendResult.textContent = "Applying storage backend and scheduling background reindex...";

        try {
            const response = await fetch("/storage-config", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ backend: backendInput.value }),
            });
            const payload = await response.json();

            if (!response.ok) {
                const errorMessage = payload.detail ?? "Storage backend update failed.";
                storageBackendResult.className = "upload-result error-text";
                storageBackendResult.textContent = errorMessage;
                return;
            }

            storageBackendResult.className = "upload-result success-text";
            storageBackendResult.textContent =
                `Active backend=${payload.current_backend}. ${payload.reindex_message}`;
            void refreshReindexStatus();
            window.setTimeout(() => {
                window.location.reload();
            }, 300);
        } catch {
            storageBackendResult.className = "upload-result error-text";
            storageBackendResult.textContent =
                "Storage backend update failed because the server did not respond.";
        }
    });
}

if (reindexStatusBadge instanceof HTMLElement) {
    if (refreshReindexStatusButton instanceof HTMLButtonElement) {
        refreshReindexStatusButton.addEventListener("click", () => {
            void refreshReindexStatus();
        });
    }
    if (startReindexButton instanceof HTMLButtonElement) {
        startReindexButton.addEventListener("click", () => {
            void startReindexFromUi();
        });
    }
    void refreshReindexStatus();
    window.setInterval(() => {
        void refreshReindexStatus();
    }, 4000);
}
