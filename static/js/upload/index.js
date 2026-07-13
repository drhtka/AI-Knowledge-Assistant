import {
    clearUploadFileButton,
    uploadDropzone,
    uploadDropzoneSubtitle,
    uploadDropzoneTitle,
    uploadForm,
    uploadResult,
    uploadSelectedFile,
} from "../dom/elements.js";
import {
    supportedUploadExtensions,
    uploadErrorResetDelayMs,
    uploadResultBaseClass,
} from "../shared/constants.js";
import {
    clearUploadStatusResetTimer,
    setUploadStatusResetTimer,
} from "../shared/state.js";
import { fillQuestionInput } from "../ask/index.js";
import { refreshReindexStatus } from "../system/reindex.js";

export function resetUploadStatus() {
    if (!(uploadResult instanceof HTMLElement)) {
        return;
    }

    clearUploadStatusResetTimer();
    uploadResult.className = uploadResultBaseClass;
    uploadResult.textContent = "";
}

export function renderUploadStatus(message, className = "upload-result meta") {
    if (!(uploadResult instanceof HTMLElement)) {
        return;
    }

    clearUploadStatusResetTimer();
    uploadResult.className = className;
    uploadResult.textContent = message;

    if (className.includes("error-text")) {
        setUploadStatusResetTimer(
            window.setTimeout(() => {
                resetUploadStatus();
            }, uploadErrorResetDelayMs),
        );
    }
}

export function getSelectedUploadExtension(fileInput) {
    if (!(fileInput instanceof HTMLInputElement) || !fileInput.files || fileInput.files.length === 0) {
        return "";
    }

    const fileName = fileInput.files[0].name.toLowerCase();
    const dotIndex = fileName.lastIndexOf(".");
    return dotIndex >= 0 ? fileName.slice(dotIndex) : "";
}

export function isSupportedUploadFile(fileInput) {
    return supportedUploadExtensions.includes(getSelectedUploadExtension(fileInput));
}

export function syncClearUploadButton(fileInput) {
    if (!(clearUploadFileButton instanceof HTMLButtonElement)) {
        return;
    }

    const hasFile =
        fileInput instanceof HTMLInputElement && Boolean(fileInput.files) && fileInput.files.length > 0;

    clearUploadFileButton.hidden = !hasFile;
}

export function syncUploadDropzoneState(fileInput) {
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

export function renderUploadSuccess(payload) {
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

export function initializeUploadPage() {
    if (uploadResult instanceof HTMLElement && uploadResult.classList.contains("error-text")) {
        setUploadStatusResetTimer(
            window.setTimeout(() => {
                resetUploadStatus();
            }, uploadErrorResetDelayMs),
        );
    }

    if (!(uploadForm instanceof HTMLFormElement) || !(uploadResult instanceof HTMLElement)) {
        return;
    }

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
