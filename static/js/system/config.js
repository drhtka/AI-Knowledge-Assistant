import {
    chunkingPresetForm,
    chunkingResult,
    mainFlowChunkingPreset,
    mainFlowPresetResult,
    runtimeSummaryMode,
    runtimeSummaryPreset,
    runtimeSummaryTopK,
    storageBackendForm,
    storageBackendResult,
} from "../dom/elements.js";
import {
    chunkingResultBaseClass,
    presetStatusResetDelayMs,
    storageBackendReloadDelayMs,
    storageBackendStatusResetDelayMs,
} from "../shared/constants.js";
import {
    clearPresetStatusResetTimer,
    clearStorageBackendStatusResetTimer,
    setPresetStatusResetTimer,
    setStorageBackendStatusResetTimer,
} from "../shared/state.js";
import { refreshReindexStatus } from "./reindex.js";

export function getPresetLabel(presetValue) {
    if (typeof presetValue !== "string" || !presetValue.trim()) {
        return "";
    }

    return presetValue.split("_", 1)[0];
}

export function setPresetStatus(resultElement, message, tone = "meta") {
    if (!(resultElement instanceof HTMLElement)) {
        return;
    }

    clearPresetStatusResetTimer();

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
        setPresetStatusResetTimer(
            window.setTimeout(() => {
                setPresetStatus(resultElement, "", "meta");
            }, presetStatusResetDelayMs),
        );
    }
}

function setStorageBackendStatus(message, tone = "meta") {
    if (!(storageBackendResult instanceof HTMLElement)) {
        return;
    }

    clearStorageBackendStatusResetTimer();

    const baseClass =
        storageBackendResult.dataset.baseClass ||
        "upload-result compact-control-result-slot system-runtime-result";
    storageBackendResult.dataset.baseClass = baseClass;

    if (tone === "error") {
        storageBackendResult.className = `${baseClass} error-text`;
    } else if (tone === "success") {
        storageBackendResult.className = `${baseClass} success-text`;
    } else {
        storageBackendResult.className = `${baseClass} meta`;
    }

    storageBackendResult.textContent = message;

    if (tone !== "meta") {
        setStorageBackendStatusResetTimer(
            window.setTimeout(() => {
                setStorageBackendStatus("", "meta");
            }, storageBackendStatusResetDelayMs),
        );
    }
}

function setStorageBackendDisabledState(disabled) {
    if (!(storageBackendForm instanceof HTMLFormElement)) {
        return;
    }

    const backendInput = storageBackendForm.elements.namedItem("storage_backend");
    if (backendInput instanceof HTMLSelectElement) {
        backendInput.disabled = disabled;
    }

    const customSelect = storageBackendForm.querySelector(".system-custom-select");
    if (!(customSelect instanceof HTMLElement)) {
        return;
    }

    customSelect.classList.toggle("is-disabled", disabled);
    customSelect.classList.toggle("is-busy", disabled);

    const trigger = customSelect.querySelector(".custom-select-trigger");
    if (trigger instanceof HTMLButtonElement) {
        trigger.disabled = disabled;
        trigger.setAttribute("aria-busy", disabled ? "true" : "false");
    }

    customSelect.querySelectorAll(".custom-select-option").forEach((option) => {
        if (option instanceof HTMLButtonElement) {
            option.disabled = disabled;
        }
    });

    if (disabled) {
        customSelect.classList.remove("is-open");
        if (trigger instanceof HTMLButtonElement) {
            trigger.setAttribute("aria-expanded", "false");
        }
    }
}

export async function applyChunkingPresetSelection(
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

        setPresetStatus(resultElement, successMessage, "success");
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

export function syncMainFlowRuntimeSummary() {
    const retrievalModeInput = document.getElementById("retrieval_mode");
    const topKInput = document.getElementById("top_k");

    if (runtimeSummaryMode instanceof HTMLElement && retrievalModeInput instanceof HTMLSelectElement) {
        runtimeSummaryMode.textContent = retrievalModeInput.value;
    }

    if (runtimeSummaryTopK instanceof HTMLElement && topKInput instanceof HTMLSelectElement) {
        runtimeSummaryTopK.textContent = topKInput.value;
    }
}

export function initializeChunkingControls() {
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
}

export function initializeStorageBackendControls() {
    if (!(storageBackendForm instanceof HTMLFormElement) || !(storageBackendResult instanceof HTMLElement)) {
        return;
    }

    storageBackendResult.dataset.baseClass = "upload-result compact-control-result-slot system-runtime-result";

    const backendInput = storageBackendForm.elements.namedItem("storage_backend");

    if (!(backendInput instanceof HTMLSelectElement)) {
        return;
    }

    backendInput.addEventListener("change", async () => {
        setStorageBackendDisabledState(true);
        setStorageBackendStatus("Applying storage backend and scheduling background reindex...");

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
                setStorageBackendStatus(errorMessage, "error");
                return;
            }

            setStorageBackendStatus(
                `Active backend=${payload.current_backend}. ${payload.reindex_message}`,
                "success",
            );
            void refreshReindexStatus();
            window.setTimeout(() => {
                window.location.reload();
            }, storageBackendReloadDelayMs);
        } catch {
            setStorageBackendStatus(
                "Storage backend update failed because the server did not respond.",
                "error",
            );
            setStorageBackendDisabledState(false);
        }
    });
}
