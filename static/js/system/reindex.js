import {
    reindexChunkCount,
    reindexDocumentCount,
    reindexElapsedMs,
    reindexFinishedAt,
    reindexRerunRequested,
    reindexStartedAt,
    reindexStatusBadge,
    reindexStatusMessage,
    reindexTrigger,
    refreshReindexStatusButton,
    startReindexButton,
} from "../dom/elements.js";
import { syncStorageBackendLockByReindexState } from "./config.js";

export function updateReindexBadge(state) {
    if (!(reindexStatusBadge instanceof HTMLElement)) {
        return;
    }

    reindexStatusBadge.textContent = state;
    reindexStatusBadge.className = `dashboard-badge reindex-badge reindex-badge-${state}`;
}

export function renderReindexStatus(payload) {
    if (!(reindexStatusBadge instanceof HTMLElement)) {
        return;
    }

    const reindexState = payload.state ?? "idle";
    updateReindexBadge(reindexState);
    syncStorageBackendLockByReindexState(reindexState);

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

export function renderReindexMessage(message, isError = false) {
    if (!(reindexStatusMessage instanceof HTMLElement)) {
        return;
    }

    reindexStatusMessage.textContent = message;
    reindexStatusMessage.classList.toggle("reindex-status-error", isError);
}

export async function refreshReindexStatus() {
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

export async function startReindexFromUi() {
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

export function initializeReindexControls() {
    if (!(reindexStatusBadge instanceof HTMLElement)) {
        return;
    }

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
