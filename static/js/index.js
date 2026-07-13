const questionForm = document.getElementById("question-form");
const clearFormButton = document.getElementById("clear-form");
const questionClearButton = document.getElementById("question-clear-button");
const demoButtons = document.querySelectorAll("[data-demo-question]");
const askResultContent = document.getElementById("ask-result-content");
const searchResultContent = document.getElementById("search-result-content");
const modeComparisonContent = document.getElementById("mode-comparison-content");
const uploadForm = document.getElementById("upload-form");
const uploadResult = document.getElementById("upload-result");
const clearUploadFileButton = document.getElementById("clear-upload-file-button");
const openUploadSuccessModalButton = document.getElementById("open-upload-success-modal-button");
const uploadSuccessModal = document.getElementById("upload-success-modal");
const externalSearchInput = document.getElementById("web_question");
const externalSearchClearButton = document.getElementById("external-search-clear-button");
const uploadDropzone = document.getElementById("upload-dropzone");
const uploadSelectedFile = document.getElementById("upload-selected-file");
const uploadDropzoneTitle = document.getElementById("upload-dropzone-title");
const uploadDropzoneSubtitle = document.getElementById("upload-dropzone-subtitle");
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
    return questionInput instanceof HTMLInputElement || questionInput instanceof HTMLTextAreaElement
        ? questionInput
        : null;
}

function getQuestionSubmitButton() {
    if (!(questionForm instanceof HTMLFormElement)) {
        return null;
    }

    const submitButton = questionForm.querySelector('button[type="submit"]');
    return submitButton instanceof HTMLButtonElement ? submitButton : null;
}

function getQuestionClearButton() {
    return questionClearButton instanceof HTMLButtonElement
        ? questionClearButton
        : clearFormButton instanceof HTMLButtonElement
          ? clearFormButton
          : null;
}

function getNormalizedQuestionValue() {
    const questionInput = getQuestionInput();
    return questionInput instanceof HTMLInputElement || questionInput instanceof HTMLTextAreaElement
        ? questionInput.value.trim()
        : "";
}

function syncQuestionActionState() {
    const hasQuestionValue = Boolean(getNormalizedQuestionValue());
    const submitButton = getQuestionSubmitButton();
    const clearButton = getQuestionClearButton();
    const questionInput = getQuestionInput();
    const canClear = hasQuestionValue && !(questionInput instanceof HTMLTextAreaElement && questionInput.readOnly);

    if (submitButton instanceof HTMLButtonElement) {
        submitButton.disabled = !hasQuestionValue;
    }

    if (clearButton instanceof HTMLButtonElement) {
        clearButton.disabled = !canClear;
        clearButton.classList.toggle("is-active", canClear);
    }
}

function replaceUrlWithoutQuestionParams() {
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.delete("question");
    nextUrl.searchParams.delete("top_k");
    nextUrl.searchParams.delete("retrieval_mode");
    nextUrl.searchParams.delete("web_question");
    nextUrl.searchParams.delete("web_top_k");
    window.history.replaceState({}, "", nextUrl.pathname + nextUrl.search);
}

function replaceUrlWithQuestionParams(questionValue, retrievalModeValue, topKValue) {
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set("question", questionValue);
    nextUrl.searchParams.set("retrieval_mode", retrievalModeValue);
    nextUrl.searchParams.set("top_k", topKValue);
    nextUrl.searchParams.delete("web_question");
    nextUrl.searchParams.delete("web_top_k");
    window.history.replaceState({}, "", nextUrl.pathname + nextUrl.search);
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function renderAskResultContent(payload) {
    if (!(askResultContent instanceof HTMLElement)) {
        return;
    }

    if (!payload) {
        askResultContent.innerHTML = `
            <p class="meta">
                Поставте запитання, щоб переглянути обґрунтовану відповідь із посиланнями
                на контекст.
            </p>
        `;
        return;
    }

    const sourcesMarkup = payload.sources
        .map((source) => `<li>${escapeHtml(source)}</li>`)
        .join("");

    askResultContent.innerHTML = `
        <p>${escapeHtml(payload.answer)}</p>
        <p class="meta">
            впевненість=${escapeHtml(payload.confidence)} | затримка_мс=${escapeHtml(payload.latency_ms)} |
            режим=${escapeHtml(payload.answer_mode)} | пошук=${escapeHtml(payload.retrieval_mode)}
        </p>
        <h3>Джерела</h3>
        <ul class="list-reset">${sourcesMarkup}</ul>
    `;
}

function renderSearchResultContent(payload) {
    if (!(searchResultContent instanceof HTMLElement)) {
        return;
    }

    if (!payload || !Array.isArray(payload.hits) || payload.hits.length === 0) {
        const retrievalModeLine = payload
            ? `<p class="meta">режим_пошуку=${escapeHtml(payload.retrieval_mode)}</p>`
            : "";
        searchResultContent.innerHTML = `
            ${retrievalModeLine}
            <p class="meta">
                Поставте запитання, щоб переглянути знайдений контекст.
            </p>
        `;
        return;
    }

    const hitsMarkup = payload.hits
        .map(
            (hit) => `
                <li>
                    <strong>${escapeHtml(hit.title)}</strong><br />
                    <span class="meta">
                        файл=${escapeHtml(hit.source_name)} | фрагмент=${escapeHtml(hit.chunk_index)} |
                        тип=${escapeHtml(hit.file_type)} | оцінка=${escapeHtml(hit.score)}
                    </span>
                    <br />
                    ${escapeHtml(hit.snippet)}
                </li>
            `,
        )
        .join("");

    searchResultContent.innerHTML = `
        <p class="meta">режим_пошуку=${escapeHtml(payload.retrieval_mode)}</p>
        <ul class="list-reset">${hitsMarkup}</ul>
    `;
}

function renderModeComparisonContent(payload) {
    if (!(modeComparisonContent instanceof HTMLElement)) {
        return;
    }

    const items = payload?.items;
    if (!Array.isArray(items) || items.length === 0) {
        modeComparisonContent.innerHTML = `
            <p class="meta">
                Поставте запитання, щоб порівняти \`auto\`, \`tfidf\` та \`embeddings\`
                поруч.
            </p>
        `;
        return;
    }

    const itemsMarkup = items
        .map(
            (item) => `
                <div class="mode-compare-card">
                    <h3>${escapeHtml(item.mode)}</h3>
                    <p class="meta">топ_джерело=${escapeHtml(item.top_source)}</p>
                    <p class="meta">топ_оцінка=${escapeHtml(item.top_score)}</p>
                    <p class="meta">збігів=${escapeHtml(item.hit_count)}</p>
                </div>
            `,
        )
        .join("");

    modeComparisonContent.innerHTML = `<div class="mode-compare-grid">${itemsMarkup}</div>`;
}

function renderQuestionLoadingState() {
    if (askResultContent instanceof HTMLElement) {
        askResultContent.innerHTML = '<p class="meta">Готуємо відповідь...</p>';
    }
    if (searchResultContent instanceof HTMLElement) {
        searchResultContent.innerHTML = '<p class="meta">Шукаємо релевантний контекст...</p>';
    }
    if (modeComparisonContent instanceof HTMLElement) {
        modeComparisonContent.innerHTML = '<p class="meta">Порівнюємо режими пошуку...</p>';
    }
}

function resetQuestionResultState() {
    renderAskResultContent(null);
    renderSearchResultContent(null);
    renderModeComparisonContent(null);
}

async function submitQuestionWithFetch(questionValue) {
    const retrievalModeInput = document.getElementById("retrieval_mode");
    const topKInput = document.getElementById("top_k");
    const submitButton = getQuestionSubmitButton();
    const clearButton = getQuestionClearButton();
    const questionInput = getQuestionInput();
    const payload = {
        question: questionValue,
        retrieval_mode:
            retrievalModeInput instanceof HTMLSelectElement ? retrievalModeInput.value : "auto",
        top_k: topKInput instanceof HTMLSelectElement ? Number(topKInput.value) : 3,
    };

    if (submitButton instanceof HTMLButtonElement) {
        submitButton.disabled = true;
    }
    if (clearButton instanceof HTMLButtonElement) {
        clearButton.disabled = true;
    }

    renderQuestionLoadingState();

    try {
        const [askResponse, searchResponse, modeComparisonResponse] = await Promise.all([
            fetch("/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            }),
            fetch("/search", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            }),
            fetch("/mode-comparison", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            }),
        ]);

        if (!askResponse.ok || !searchResponse.ok || !modeComparisonResponse.ok) {
            throw new Error("question_fetch_failed");
        }

        const [askPayload, searchPayload, modeComparisonPayload] = await Promise.all([
            askResponse.json(),
            searchResponse.json(),
            modeComparisonResponse.json(),
        ]);

        renderAskResultContent(askPayload);
        renderSearchResultContent(searchPayload);
        renderModeComparisonContent(modeComparisonPayload);
        replaceUrlWithQuestionParams(questionValue, payload.retrieval_mode, String(payload.top_k));

        if (questionInput instanceof HTMLInputElement || questionInput instanceof HTMLTextAreaElement) {
            questionInput.value = "";
            questionInput.focus();
        }
    } catch {
        if (askResultContent instanceof HTMLElement) {
            askResultContent.innerHTML =
                '<p class="error-text">Не вдалося отримати відповідь. Спробуйте ще раз.</p>';
        }
        if (searchResultContent instanceof HTMLElement) {
            searchResultContent.innerHTML =
                '<p class="error-text">Не вдалося оновити знайдений контекст.</p>';
        }
        if (modeComparisonContent instanceof HTMLElement) {
            modeComparisonContent.innerHTML =
                '<p class="error-text">Не вдалося оновити порівняння режимів.</p>';
        }
    } finally {
        syncQuestionActionState();
    }
}

function fillQuestionInput(questionText) {
    if (!(questionForm instanceof HTMLFormElement)) {
        const nextUrl = new URL(window.location.origin + "/");
        nextUrl.searchParams.set("question", questionText);
        window.location.assign(nextUrl.toString());
        return;
    }

    const questionInput = getQuestionInput();
    if (questionInput instanceof HTMLInputElement || questionInput instanceof HTMLTextAreaElement) {
        questionInput.value = questionText;
        syncQuestionActionState();
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

function syncUploadDropzoneState(fileInput) {
    const selectedFileName =
        fileInput instanceof HTMLInputElement && fileInput.files && fileInput.files.length > 0
            ? fileInput.files[0].name
            : "";

    if (uploadDropzone instanceof HTMLElement) {
        uploadDropzone.classList.toggle("has-file", Boolean(selectedFileName));
    }

    if (uploadDropzoneTitle instanceof HTMLElement) {
        uploadDropzoneTitle.textContent = selectedFileName || "Перетягніть файл сюди";
    }

    if (uploadDropzoneSubtitle instanceof HTMLElement) {
        uploadDropzoneSubtitle.textContent = selectedFileName
            ? "Файл готовий до завантаження"
            : "або натисніть, щоб вибрати документ";
    }

    if (uploadSelectedFile instanceof HTMLElement) {
        uploadSelectedFile.textContent = selectedFileName
            ? `Вибрано файл: ${selectedFileName}`
            : "Файл ще не вибрано.";
    }
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

    const message = document.createElement("p");
    message.className = "meta";
    message.textContent = "Details are available in the modal window.";

    const actions = document.createElement("div");
    actions.className = "actions upload-result-actions";

    const openButton = document.createElement("button");
    openButton.type = "button";
    openButton.textContent = "View Details";

    const modal = document.createElement("div");
    modal.id = "upload-success-modal";
    modal.className = "upload-success-modal is-open";
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-modal", "true");
    modal.setAttribute("aria-labelledby", "upload-success-modal-title");

    const backdrop = document.createElement("div");
    backdrop.className = "upload-success-modal-backdrop";
    backdrop.dataset.closeUploadModal = "true";

    const dialog = document.createElement("div");
    dialog.className = "upload-success-modal-dialog";

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "upload-success-modal-close";
    closeButton.setAttribute("aria-label", "Close modal");
    closeButton.dataset.closeUploadModal = "true";
    closeButton.textContent = "×";

    const body = document.createElement("div");
    body.className = "upload-success-modal-body";

    const modalTitle = document.createElement("strong");
    modalTitle.id = "upload-success-modal-title";
    modalTitle.textContent = "Document uploaded successfully";

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

    const quickPromptActions = document.createElement("div");
    quickPromptActions.className = "actions upload-result-actions";

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
            modal.classList.remove("is-open");
        });
        quickPromptActions.append(promptButton);
    });

    const closeModal = () => {
        modal.classList.remove("is-open");
    };

    openButton.addEventListener("click", () => {
        modal.classList.add("is-open");
    });

    modal.addEventListener("click", (event) => {
        const target = event.target instanceof HTMLElement ? event.target : null;
        if (target?.dataset.closeUploadModal === "true") {
            closeModal();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && modal.classList.contains("is-open")) {
            closeModal();
        }
    });

    actions.append(openButton);
    body.append(modalTitle, details, followUp);

    if (previewBlock instanceof HTMLDivElement) {
        body.append(previewBlock);
    }

    body.append(quickPromptActions);
    dialog.append(closeButton, body);
    modal.append(backdrop, dialog);
    uploadResult.append(title, message, actions, modal);
}

demoButtons.forEach((button) => {
    button.addEventListener("click", () => {
        fillQuestionInput(button.dataset.demoQuestion ?? "");
    });
});

if (questionForm instanceof HTMLFormElement) {
    const questionInput = getQuestionInput();

    syncQuestionActionState();

    if (
        (questionInput instanceof HTMLInputElement || questionInput instanceof HTMLTextAreaElement) &&
        !questionInput.readOnly
    ) {
        questionInput.addEventListener("input", () => {
            syncQuestionActionState();
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

if (clearFormButton && questionForm) {
    clearFormButton.addEventListener("click", () => {
        const questionInput = getQuestionInput();
        if (questionInput instanceof HTMLInputElement || questionInput instanceof HTMLTextAreaElement) {
            questionInput.value = "";
        }
        syncQuestionActionState();
        replaceUrlWithoutQuestionParams();
        resetQuestionResultState();

        if (questionInput instanceof HTMLInputElement || questionInput instanceof HTMLTextAreaElement) {
            questionInput.focus();
        }
    });
}

if (uploadForm instanceof HTMLFormElement && uploadResult instanceof HTMLElement) {
    const fileInput = uploadForm.elements.namedItem("file");

    if (fileInput instanceof HTMLInputElement) {
        syncClearUploadButton(fileInput);
        syncUploadDropzoneState(fileInput);

        fileInput.addEventListener("change", () => {
            syncClearUploadButton(fileInput);
            syncUploadDropzoneState(fileInput);

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

        const applyDroppedFiles = (files) => {
            if (!(files instanceof FileList) || files.length === 0) {
                return;
            }

            fileInput.files = files;
            syncClearUploadButton(fileInput);
            syncUploadDropzoneState(fileInput);
            fileInput.dispatchEvent(new Event("change", { bubbles: true }));
        };

        if (uploadDropzone instanceof HTMLElement && !fileInput.disabled) {
            ["dragenter", "dragover"].forEach((eventName) => {
                uploadDropzone.addEventListener(eventName, (event) => {
                    event.preventDefault();
                    uploadDropzone.classList.add("is-dragover");
                });
            });

            ["dragleave", "dragend"].forEach((eventName) => {
                uploadDropzone.addEventListener(eventName, () => {
                    uploadDropzone.classList.remove("is-dragover");
                });
            });

            uploadDropzone.addEventListener("drop", (event) => {
                event.preventDefault();
                uploadDropzone.classList.remove("is-dragover");

                if (!(event.dataTransfer instanceof DataTransfer)) {
                    return;
                }

                const transfer = new DataTransfer();
                const [firstFile] = Array.from(event.dataTransfer.files);

                if (!firstFile) {
                    return;
                }

                transfer.items.add(firstFile);
                applyDroppedFiles(transfer.files);
            });
        }
    }

    if (clearUploadFileButton instanceof HTMLButtonElement && fileInput instanceof HTMLInputElement) {
        clearUploadFileButton.addEventListener("click", () => {
            uploadForm.reset();
            syncClearUploadButton(fileInput);
            syncUploadDropzoneState(fileInput);
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
            syncUploadDropzoneState(fileInput);
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

if (externalSearchInput instanceof HTMLTextAreaElement && externalSearchClearButton instanceof HTMLButtonElement) {
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

function initializeCustomSelects(rootSelector) {
    const customSelects = document.querySelectorAll(rootSelector);
    customSelects.forEach((customSelect) => {
        if (!(customSelect instanceof HTMLElement)) {
            return;
        }

        const trigger = customSelect.querySelector(".custom-select-trigger");
        const valueElement = customSelect.querySelector(".custom-select-value");
        const nativeSelect = customSelect.querySelector(".custom-select-native");
        const options = customSelect.querySelectorAll(".custom-select-option");

        if (
            !(trigger instanceof HTMLButtonElement) ||
            !(valueElement instanceof HTMLElement) ||
            !(nativeSelect instanceof HTMLSelectElement)
        ) {
            return;
        }

        const closeDropdown = () => {
            customSelect.classList.remove("is-open");
            trigger.setAttribute("aria-expanded", "false");
        };

        const openDropdown = () => {
            document.querySelectorAll(`${rootSelector}.is-open`).forEach((node) => {
                if (node instanceof HTMLElement && node !== customSelect) {
                    node.classList.remove("is-open");
                    const otherTrigger = node.querySelector(".custom-select-trigger");
                    if (otherTrigger instanceof HTMLButtonElement) {
                        otherTrigger.setAttribute("aria-expanded", "false");
                    }
                }
            });
            customSelect.classList.add("is-open");
            trigger.setAttribute("aria-expanded", "true");
        };

        const syncSelectedOption = (nextValue) => {
            nativeSelect.value = nextValue;
            const selectedOption = nativeSelect.selectedOptions[0];
            valueElement.textContent = selectedOption ? selectedOption.textContent ?? "" : "";
            options.forEach((option) => {
                if (!(option instanceof HTMLButtonElement)) {
                    return;
                }
                const isSelected = option.dataset.value === nextValue;
                option.classList.toggle("is-selected", isSelected);
                option.setAttribute("aria-selected", isSelected ? "true" : "false");
            });
        };

        trigger.addEventListener("click", () => {
            if (trigger.disabled) {
                return;
            }
            if (customSelect.classList.contains("is-open")) {
                closeDropdown();
                return;
            }
            openDropdown();
        });

        options.forEach((option) => {
            if (!(option instanceof HTMLButtonElement)) {
                return;
            }
            option.addEventListener("click", () => {
                if (option.disabled) {
                    return;
                }
                const nextValue = option.dataset.value ?? "";
                syncSelectedOption(nextValue);
                nativeSelect.dispatchEvent(new Event("change", { bubbles: true }));
                closeDropdown();
            });
        });

        document.addEventListener("click", (event) => {
            if (!customSelect.contains(event.target instanceof Node ? event.target : null)) {
                closeDropdown();
            }
        });

        trigger.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeDropdown();
                trigger.blur();
            }
        });
    });
}

initializeCustomSelects(".ask-settings-row-in-composer .custom-select");
initializeCustomSelects(".system-runtime-form-row .custom-select");
initializeCustomSelects(".chunking-custom-form-row .custom-select");

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
