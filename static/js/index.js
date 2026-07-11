const questionForm = document.getElementById("question-form");
const clearFormButton = document.getElementById("clear-form");
const demoButtons = document.querySelectorAll("[data-demo-question]");
const uploadForm = document.getElementById("upload-form");
const uploadResult = document.getElementById("upload-result");
const clearUploadFileButton = document.getElementById("clear-upload-file-button");
const mainFlowChunkingPreset = document.getElementById("main_flow_chunking_preset");
const mainFlowPresetResult = document.getElementById("main-flow-preset-result");
const runtimeSummaryMode = document.getElementById("runtime-summary-mode");
const runtimeSummaryPreset = document.getElementById("runtime-summary-preset");
const runtimeSummaryTopK = document.getElementById("runtime-summary-top-k");
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
const uploadResultBaseClass = "upload-result meta workflow-result-slot";
const chunkingResultBaseClass = "upload-result workflow-result-slot chunking-result-slot";
const supportedUploadExtensions = [".txt", ".md", ".pdf"];
const uploadErrorResetDelayMs = 3500;
const presetStatusResetDelayMs = 3500;
let uploadStatusResetTimerId = null;
let presetStatusResetTimerId = null;

function getQuestionInput() {
    if (!(questionForm instanceof HTMLFormElement)) {
        return null;
    }

    const questionInput = questionForm.elements.namedItem("question");
    return questionInput instanceof HTMLInputElement ? questionInput : null;
}

function getQuestionSubmitButton() {
    if (!(questionForm instanceof HTMLFormElement)) {
        return null;
    }

    const submitButton = questionForm.querySelector('button[type="submit"]');
    return submitButton instanceof HTMLButtonElement ? submitButton : null;
}

function getNormalizedQuestionValue() {
    const questionInput = getQuestionInput();
    return questionInput instanceof HTMLInputElement ? questionInput.value.trim() : "";
}

function syncQuestionSubmitState() {
    const submitButton = getQuestionSubmitButton();
    if (!(submitButton instanceof HTMLButtonElement)) {
        return;
    }

    submitButton.disabled = !getNormalizedQuestionValue();
}

function fillQuestionInput(questionText) {
    if (!(questionForm instanceof HTMLFormElement)) {
        const nextUrl = new URL(window.location.origin + "/");
        nextUrl.searchParams.set("question", questionText);
        window.location.assign(nextUrl.toString());
        return;
    }

    const questionInput = getQuestionInput();
    if (questionInput instanceof HTMLInputElement) {
        questionInput.value = questionText;
        syncQuestionSubmitState();
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

    if (uploadStatusResetTimerId !== null) {
        window.clearTimeout(uploadStatusResetTimerId);
        uploadStatusResetTimerId = null;
    }

    uploadResult.className = className;
    uploadResult.textContent = message;

    if (className.includes("error-text")) {
        uploadStatusResetTimerId = window.setTimeout(() => {
            resetUploadStatus();
        }, uploadErrorResetDelayMs);
    }
}

function resetUploadStatus() {
    if (!(uploadResult instanceof HTMLElement)) {
        return;
    }

    if (uploadStatusResetTimerId !== null) {
        window.clearTimeout(uploadStatusResetTimerId);
        uploadStatusResetTimerId = null;
    }

    uploadResult.className = uploadResultBaseClass;
    uploadResult.textContent = "";
}

function getSelectedUploadExtension(fileInput) {
    if (!(fileInput instanceof HTMLInputElement) || !fileInput.files || fileInput.files.length === 0) {
        return "";
    }

    const fileName = fileInput.files[0].name.toLowerCase();
    const dotIndex = fileName.lastIndexOf(".");
    return dotIndex >= 0 ? fileName.slice(dotIndex) : "";
}

function isSupportedUploadFile(fileInput) {
    return supportedUploadExtensions.includes(getSelectedUploadExtension(fileInput));
}

function getPresetLabel(presetValue) {
    if (typeof presetValue !== "string" || !presetValue.trim()) {
        return "";
    }

    return presetValue.split("_", 1)[0];
}

function setPresetStatus(resultElement, message, tone = "meta") {
    if (!(resultElement instanceof HTMLElement)) {
        return;
    }

    if (presetStatusResetTimerId !== null) {
        window.clearTimeout(presetStatusResetTimerId);
        presetStatusResetTimerId = null;
    }

    const baseClass = resultElement.dataset.baseClass || resultElement.className;
    resultElement.dataset.baseClass = baseClass;

    if (tone === "error") {
        resultElement.className = `${baseClass} error-text`;
    } else if (tone === "success") {
        resultElement.className = `${baseClass} success-text`;
    } else {
        resultElement.className = `${baseClass} meta`;
    }

    resultElement.textContent = message;

    if (resultElement === mainFlowPresetResult && tone !== "meta") {
        presetStatusResetTimerId = window.setTimeout(() => {
            setPresetStatus(resultElement, "", "meta");
        }, presetStatusResetDelayMs);
    }
}

async function applyChunkingPresetSelection(
    presetInput,
    resultElement,
    { reloadOnSuccess = false, buildSuccessMessage = null } = {},
) {
    if (!(presetInput instanceof HTMLSelectElement)) {
        return;
    }

    presetInput.disabled = true;
    setPresetStatus(resultElement, "Applying chunking preset and scheduling background reindex...");

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
            setPresetStatus(resultElement, errorMessage, "error");
            return;
        }

        const presetLabel = getPresetLabel(payload.current_preset) || presetInput.value;
        if (runtimeSummaryPreset instanceof HTMLElement) {
            runtimeSummaryPreset.textContent = presetLabel;
        }

        const successMessage =
            typeof buildSuccessMessage === "function"
                ? buildSuccessMessage(payload, presetLabel)
                : `Preset updated: ${presetLabel}. ${payload.reindex_message}`;

        setPresetStatus(
            resultElement,
            successMessage,
            "success",
        );

        void refreshReindexStatus();

        if (reloadOnSuccess) {
            window.setTimeout(() => {
                window.location.reload();
            }, 2200);
        }
    } catch {
        setPresetStatus(
            resultElement,
            "Preset update failed because the server did not respond.",
            "error",
        );
    } finally {
        presetInput.disabled = false;
    }
}

function syncClearUploadButton(fileInput) {
    if (!(clearUploadFileButton instanceof HTMLButtonElement)) {
        return;
    }

    const hasFile =
        fileInput instanceof HTMLInputElement && Boolean(fileInput.files) && fileInput.files.length > 0;

    clearUploadFileButton.hidden = !hasFile;
}

function syncMainFlowRuntimeSummary() {
    const retrievalModeInput = document.getElementById("retrieval_mode");
    const topKInput = document.getElementById("top_k");

    if (runtimeSummaryMode instanceof HTMLElement && retrievalModeInput instanceof HTMLSelectElement) {
        runtimeSummaryMode.textContent = retrievalModeInput.value;
    }

    if (runtimeSummaryTopK instanceof HTMLElement && topKInput instanceof HTMLSelectElement) {
        runtimeSummaryTopK.textContent = topKInput.value;
    }
}

if (uploadResult instanceof HTMLElement && uploadResult.classList.contains("error-text")) {
    uploadStatusResetTimerId = window.setTimeout(() => {
        resetUploadStatus();
    }, uploadErrorResetDelayMs);
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

if (questionForm instanceof HTMLFormElement) {
    const questionInput = getQuestionInput();

    syncQuestionSubmitState();

    if (questionInput instanceof HTMLInputElement && !questionInput.readOnly) {
        questionInput.addEventListener("input", () => {
            syncQuestionSubmitState();
        });
    }

    questionForm.addEventListener("submit", (event) => {
        const questionValue = getNormalizedQuestionValue();

        if (!questionValue) {
            event.preventDefault();

            const nextUrl = new URL(window.location.href);
            nextUrl.searchParams.delete("question");
            nextUrl.searchParams.delete("top_k");
            nextUrl.searchParams.delete("retrieval_mode");
            nextUrl.searchParams.delete("web_question");
            nextUrl.searchParams.delete("web_top_k");
            window.location.assign(nextUrl.pathname + nextUrl.search);
            return;
        }

        if (questionInput instanceof HTMLInputElement) {
            questionInput.value = questionValue;
        }
    });
}

if (clearFormButton && questionForm) {
    clearFormButton.addEventListener("click", () => {
        const questionInput = getQuestionInput();
        if (questionInput instanceof HTMLInputElement) {
            questionInput.value = "";
        }
        syncQuestionSubmitState();

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
    const fileInput = uploadForm.elements.namedItem("file");

    if (fileInput instanceof HTMLInputElement) {
        syncClearUploadButton(fileInput);

        fileInput.addEventListener("change", () => {
            syncClearUploadButton(fileInput);

            if (!fileInput.files || fileInput.files.length === 0) {
                resetUploadStatus();
                return;
            }

            if (!isSupportedUploadFile(fileInput)) {
                renderUploadStatus(
                    "Only .txt, .md, and .pdf files are supported.",
                    `${uploadResultBaseClass} error-text`,
                );
                return;
            }

            resetUploadStatus();
        });
    }

    if (clearUploadFileButton instanceof HTMLButtonElement && fileInput instanceof HTMLInputElement) {
        clearUploadFileButton.addEventListener("click", () => {
            uploadForm.reset();
            syncClearUploadButton(fileInput);
            resetUploadStatus();
            fileInput.focus();
        });
    }

    uploadForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (!(fileInput instanceof HTMLInputElement) || !fileInput.files || fileInput.files.length === 0) {
            renderUploadStatus(
                "Choose a .txt, .md, or .pdf file first.",
                `${uploadResultBaseClass} error-text`,
            );
            return;
        }

        if (!isSupportedUploadFile(fileInput)) {
            renderUploadStatus(
                "Only .txt, .md, and .pdf files are supported.",
                `${uploadResultBaseClass} error-text`,
            );
            return;
        }

        const formData = new FormData();
        formData.append("file", fileInput.files[0]);

        renderUploadStatus(
            "Uploading document and scheduling background reindex...",
            uploadResultBaseClass,
        );

        try {
            const response = await fetch("/ingest", {
                method: "POST",
                body: formData,
            });
            const payload = await response.json();

            if (!response.ok) {
                const errorMessage = payload.detail ?? "Upload failed.";
                renderUploadStatus(errorMessage, `${uploadResultBaseClass} error-text`);
                return;
            }

            renderUploadSuccess(payload);
            void refreshReindexStatus();
            uploadForm.reset();
            syncClearUploadButton(fileInput);
        } catch {
            renderUploadStatus(
                "Upload failed because the server did not respond.",
                `${uploadResultBaseClass} error-text`,
            );
        }
    });
}

if (chunkingResult instanceof HTMLElement) {
    chunkingResult.dataset.baseClass = chunkingResultBaseClass;
}

if (mainFlowPresetResult instanceof HTMLElement) {
    mainFlowPresetResult.dataset.baseClass = "upload-result compact-control-result-slot";
}

if (chunkingPresetForm instanceof HTMLFormElement && chunkingResult instanceof HTMLElement) {
    const presetInput = chunkingPresetForm.elements.namedItem("chunking_preset");

    if (presetInput instanceof HTMLSelectElement) {
        presetInput.addEventListener("change", () => {
            void applyChunkingPresetSelection(presetInput, chunkingResult, {
                reloadOnSuccess: true,
                buildSuccessMessage: (payload) =>
                    `Preset updated: ${payload.chunk_size_words}/${payload.chunk_overlap_words}. ${payload.reindex_message}`,
            });
        });
    }
}

if (mainFlowChunkingPreset instanceof HTMLSelectElement && mainFlowPresetResult instanceof HTMLElement) {
    mainFlowChunkingPreset.addEventListener("change", () => {
        void applyChunkingPresetSelection(mainFlowChunkingPreset, mainFlowPresetResult);
    });
}

const retrievalModeInput = document.getElementById("retrieval_mode");
if (retrievalModeInput instanceof HTMLSelectElement) {
    retrievalModeInput.addEventListener("change", () => {
        syncMainFlowRuntimeSummary();
    });
}

const topKInput = document.getElementById("top_k");
if (topKInput instanceof HTMLSelectElement) {
    topKInput.addEventListener("change", () => {
        syncMainFlowRuntimeSummary();
    });
}

syncMainFlowRuntimeSummary();

if (storageBackendForm instanceof HTMLFormElement && storageBackendResult instanceof HTMLElement) {
    const backendInput = storageBackendForm.elements.namedItem("storage_backend");

    if (backendInput instanceof HTMLSelectElement) {
        backendInput.addEventListener("change", async () => {
            storageBackendResult.className = "upload-result meta compact-control-result-slot system-runtime-result";
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
                    storageBackendResult.className = "upload-result error-text compact-control-result-slot system-runtime-result";
                    storageBackendResult.textContent = errorMessage;
                    return;
                }

                storageBackendResult.className = "upload-result success-text compact-control-result-slot system-runtime-result";
                storageBackendResult.textContent =
                    `Active backend=${payload.current_backend}. ${payload.reindex_message}`;
                void refreshReindexStatus();
                window.setTimeout(() => {
                    window.location.reload();
                }, 300);
            } catch {
                storageBackendResult.className = "upload-result error-text compact-control-result-slot system-runtime-result";
                storageBackendResult.textContent =
                    "Storage backend update failed because the server did not respond.";
            }
        });
    }
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
