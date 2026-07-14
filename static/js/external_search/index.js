import {
    externalSearchActionsContent,
    externalSearchActivityContent,
    externalSearchClearButton,
    externalSearchForm,
    externalSearchInitialState,
    externalSearchInput,
    externalSearchResultsCard,
    externalSearchResultsContent,
    externalSearchSessionContent,
    externalSearchSubmitButton,
    webSearchResultJsonContent,
} from "../dom/elements.js";
import { escapeHtml } from "../shared/utils.js";

const minimumExternalSearchLength = 3;
const externalSearchActivityLimit = 6;

const externalSearchState = {
    question: "",
    topK: 1,
    result: null,
    error: "",
    status: "idle",
    latencyMs: null,
    updatedAt: "",
    isAuthenticated: false,
};

let isSearching = false;

function renderExternalSearchJsonDebug(payload) {
    if (!(webSearchResultJsonContent instanceof HTMLElement)) {
        return;
    }

    webSearchResultJsonContent.textContent = JSON.stringify(payload ?? {}, null, 2);
}

function focusExternalSearchResultsCard() {
    if (!(externalSearchResultsCard instanceof HTMLElement)) {
        return;
    }

    externalSearchResultsCard.scrollIntoView({ behavior: "smooth", block: "start" });
    externalSearchResultsCard.focus({ preventScroll: true });
}

function getExternalSearchTopKInputs() {
    if (!(externalSearchForm instanceof HTMLFormElement)) {
        return [];
    }

    return Array.from(externalSearchForm.querySelectorAll('input[name="web_top_k"]')).filter(
        (input) => input instanceof HTMLInputElement,
    );
}

function getNormalizedExternalSearchValue() {
    return externalSearchInput instanceof HTMLTextAreaElement
        ? externalSearchInput.value.trim()
        : "";
}

function getSelectedExternalSearchTopK() {
    const selectedInput = getExternalSearchTopKInputs().find((input) => input.checked);
    if (!(selectedInput instanceof HTMLInputElement)) {
        return 1;
    }

    const parsed = Number(selectedInput.value);
    return Number.isInteger(parsed) && parsed >= 1 ? parsed : 1;
}

function parseExternalSearchInitialState() {
    if (!(externalSearchInitialState instanceof HTMLScriptElement)) {
        return;
    }

    try {
        const payload = JSON.parse(externalSearchInitialState.textContent || "{}");
        externalSearchState.question = typeof payload.question === "string" ? payload.question : "";
        externalSearchState.topK = Number.isInteger(payload.top_k) ? payload.top_k : 1;
        externalSearchState.error = typeof payload.error === "string" ? payload.error : "";
        const parsedResult =
            payload.result && typeof payload.result === "object" && !Array.isArray(payload.result)
                ? payload.result
                : null;
        externalSearchState.result =
            parsedResult &&
            (typeof parsedResult.question === "string" ||
                Array.isArray(parsedResult.hits))
                ? parsedResult
                : null;
        externalSearchState.isAuthenticated = payload.is_authenticated === true;
        externalSearchState.status = externalSearchState.error
            ? "error"
            : externalSearchState.result
              ? "success"
              : "idle";
    } catch {
        externalSearchState.question = "";
        externalSearchState.topK = 1;
        externalSearchState.result = null;
        externalSearchState.error = "";
        externalSearchState.status = "idle";
    }
}

function formatExternalSearchTimestamp(value) {
    if (typeof value !== "string" || !value.trim()) {
        return "";
    }

    const timestamp = new Date(value);
    return Number.isNaN(timestamp.getTime()) ? value : timestamp.toLocaleString();
}

function replaceUrlWithExternalSearchParams(questionValue, topKValue) {
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set("web_question", questionValue);
    nextUrl.searchParams.set("web_top_k", String(topKValue));
    window.history.replaceState({}, "", nextUrl.pathname + nextUrl.search);
}

function replaceUrlWithoutExternalSearchParams() {
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.delete("web_question");
    nextUrl.searchParams.delete("web_top_k");
    window.history.replaceState({}, "", nextUrl.pathname + nextUrl.search);
}

function buildExternalSearchFollowUps(questionValue) {
    const normalizedQuestion = String(questionValue || "").trim();
    if (!normalizedQuestion) {
        return [];
    }

    return [
        {
            label: "Official source",
            query: `official source for ${normalizedQuestion}`,
        },
        {
            label: "Latest updates",
            query: `latest updates about ${normalizedQuestion}`,
        },
        {
            label: "Technical overview",
            query: `technical overview of ${normalizedQuestion}`,
        },
    ];
}

function renderExternalSearchActions(questionValue) {
    if (!(externalSearchActionsContent instanceof HTMLElement)) {
        return;
    }

    const followUps = buildExternalSearchFollowUps(questionValue);
    if (followUps.length === 0) {
        externalSearchActionsContent.innerHTML = `
            <p class="meta">
                Після першого запиту тут з'являться швидкі follow-up дії.
            </p>
        `;
        return;
    }

    externalSearchActionsContent.innerHTML = followUps
        .map(
            (item) => `
                <button
                    type="button"
                    data-external-search-followup="${escapeHtml(item.query)}"
                >
                    ${escapeHtml(item.label)}
                </button>
            `,
        )
        .join("");
}

function renderExternalSearchSession() {
    if (!(externalSearchSessionContent instanceof HTMLElement)) {
        return;
    }

    if (externalSearchState.status === "loading") {
        externalSearchSessionContent.innerHTML = `
            <div class="external-search-session-shell is-loading">
                <div class="external-search-session-header">
                    <div>
                        <p class="meta external-search-session-caption">Current search</p>
                        <h3 class="external-search-session-query">
                            ${escapeHtml(externalSearchState.question)}
                        </h3>
                    </div>
                    <span class="dashboard-badge external-search-status-badge is-loading">searching</span>
                </div>
                <div class="pill-row external-search-session-pills">
                    <span class="mode-pill">top_k=${escapeHtml(externalSearchState.topK)}</span>
                    <span class="mode-pill">engine=web-search</span>
                    <span class="mode-pill">status=pending</span>
                </div>
                <div class="external-search-loader" aria-live="polite">
                    <span class="external-search-loader-dots" aria-hidden="true">
                        <span></span><span></span><span></span>
                    </span>
                    <span class="meta">Виконуємо зовнішній пошук і оновлюємо джерела.</span>
                </div>
            </div>
        `;
        return;
    }

    if (externalSearchState.status === "error") {
        externalSearchSessionContent.innerHTML = `
            <div class="external-search-session-shell is-error">
                <div class="external-search-session-header">
                    <div>
                        <p class="meta external-search-session-caption">Current search</p>
                        <h3 class="external-search-session-query">
                            ${escapeHtml(externalSearchState.question)}
                        </h3>
                    </div>
                    <span class="dashboard-badge external-search-status-badge is-error">failed</span>
                </div>
                <div class="pill-row external-search-session-pills">
                    <span class="mode-pill">top_k=${escapeHtml(externalSearchState.topK)}</span>
                    <span class="mode-pill">engine=web-search</span>
                    <span class="mode-pill">hits=0</span>
                </div>
                <p class="error-text external-search-session-message">
                    ${escapeHtml(externalSearchState.error)}
                </p>
            </div>
        `;
        return;
    }

    if (externalSearchState.status === "success" && externalSearchState.result) {
        const hitCount = Array.isArray(externalSearchState.result.hits)
            ? externalSearchState.result.hits.length
            : 0;
        const latencyLine = Number.isInteger(externalSearchState.latencyMs)
            ? `latency_ms=${externalSearchState.latencyMs}`
            : "latency tracked in activity log";
        const updatedAtLine = externalSearchState.updatedAt
            ? ` | updated=${escapeHtml(formatExternalSearchTimestamp(externalSearchState.updatedAt))}`
            : "";

        externalSearchSessionContent.innerHTML = `
            <div class="external-search-session-shell is-success">
                <div class="external-search-session-header">
                    <div>
                        <p class="meta external-search-session-caption">Current search</p>
                        <h3 class="external-search-session-query">
                            ${escapeHtml(externalSearchState.result.question || externalSearchState.question)}
                        </h3>
                    </div>
                    <span class="dashboard-badge external-search-status-badge is-success">completed</span>
                </div>
                <div class="pill-row external-search-session-pills">
                    <span class="mode-pill">
                        engine=${escapeHtml(externalSearchState.result.engine || "web-search")}
                    </span>
                    <span class="mode-pill">top_k=${escapeHtml(externalSearchState.result.top_k || externalSearchState.topK)}</span>
                    <span class="mode-pill">hits=${escapeHtml(hitCount)}</span>
                </div>
                <p class="meta external-search-session-message">
                    ${latencyLine}${updatedAtLine}
                </p>
            </div>
        `;
        return;
    }

    externalSearchSessionContent.innerHTML = `
        <div class="external-search-session-shell">
            <div class="external-search-session-header">
                <div>
                    <p class="meta external-search-session-caption">Current search</p>
                    <h3 class="external-search-session-query">Search workspace is ready</h3>
                </div>
                <span class="dashboard-badge external-search-status-badge">idle</span>
            </div>
            <p class="meta external-search-session-message">
                Введіть запит вище, щоб побачити engine, top_k, hit count і
                результати без перезавантаження сторінки.
            </p>
        </div>
    `;
}

function renderExternalSearchResults() {
    if (!(externalSearchResultsContent instanceof HTMLElement)) {
        return;
    }

    if (externalSearchState.status === "loading") {
        externalSearchResultsContent.innerHTML = `
            <div class="external-search-results-empty external-search-results-loading">
                <div class="external-search-loader" aria-live="polite">
                    <span class="external-search-loader-dots" aria-hidden="true">
                        <span></span><span></span><span></span>
                    </span>
                    <span class="meta">Шукаємо релевантні зовнішні джерела.</span>
                </div>
            </div>
        `;
        return;
    }

    if (externalSearchState.status === "error") {
        externalSearchResultsContent.innerHTML = `
            <div class="external-search-results-empty">
                <p class="error-text">${escapeHtml(externalSearchState.error)}</p>
            </div>
        `;
        return;
    }

    const hits = Array.isArray(externalSearchState.result?.hits)
        ? externalSearchState.result.hits
        : [];
    if (hits.length === 0) {
        externalSearchResultsContent.innerHTML = `
            <div class="external-search-results-empty">
                <p class="meta">
                    Запустіть зовнішній вебпошук, щоб переглянути тут результати.
                </p>
            </div>
        `;
        return;
    }

    externalSearchResultsContent.innerHTML = `
        <div class="external-search-results-grid">
            ${hits
                .map(
                    (hit) => `
                        <article class="external-search-result-item">
                            <div class="external-search-result-header">
                                <div>
                                    <p class="meta external-search-result-position">
                                        result #${escapeHtml(hit.position)}
                                    </p>
                                    <h3 class="external-search-result-title">
                                        ${escapeHtml(hit.title)}
                                    </h3>
                                </div>
                                <span class="mode-pill external-search-source-pill">
                                    ${escapeHtml(hit.source || "web")}
                                </span>
                            </div>
                            <a
                                class="external-search-result-link"
                                href="${escapeHtml(hit.link)}"
                                target="_blank"
                                rel="noreferrer"
                            >
                                ${escapeHtml(hit.link)}
                            </a>
                            <p class="external-search-result-snippet">
                                ${escapeHtml(hit.snippet || "Snippet unavailable.")}
                            </p>
                        </article>
                    `,
                )
                .join("")}
        </div>
    `;
}

function renderExternalSearchActivity(entries, options = {}) {
    if (!(externalSearchActivityContent instanceof HTMLElement)) {
        return;
    }

    if (options.loading) {
        externalSearchActivityContent.innerHTML = `
            <div class="external-search-activity-empty">
                <div class="external-search-loader" aria-live="polite">
                    <span class="external-search-loader-dots" aria-hidden="true">
                        <span></span><span></span><span></span>
                    </span>
                    <span class="meta">Оновлюємо технічний журнал вебпошуку.</span>
                </div>
            </div>
        `;
        return;
    }

    if (typeof options.error === "string" && options.error.trim()) {
        externalSearchActivityContent.innerHTML = `
            <div class="external-search-activity-empty">
                <p class="meta">
                    Activity log тимчасово недоступний: ${escapeHtml(options.error)}
                </p>
            </div>
        `;
        return;
    }

    if (!Array.isArray(entries) || entries.length === 0) {
        externalSearchActivityContent.innerHTML = `
            <div class="external-search-activity-empty">
                <p class="meta">
                    Історія ще порожня. Після запиту тут з'являться status, engine,
                    top_k, hit count і latency.
                </p>
            </div>
        `;
        return;
    }

    externalSearchActivityContent.innerHTML = `
        <div class="external-search-activity-list">
            ${entries
                .map((entry) => {
                    const entryStatus = entry.status === "completed" ? "success" : "error";
                    return `
                        <article class="external-search-activity-item">
                            <div class="external-search-activity-item-header">
                                <div>
                                    <p class="meta external-search-activity-item-caption">
                                        request #${escapeHtml(entry.history_entry_id)}
                                    </p>
                                    <strong class="external-search-activity-item-title">
                                        ${escapeHtml(entry.engine)}
                                    </strong>
                                </div>
                                <span class="dashboard-badge external-search-status-badge is-${entryStatus}">
                                    ${escapeHtml(entry.status)}
                                </span>
                            </div>
                            <div class="pill-row external-search-activity-pills">
                                <span class="mode-pill">top_k=${escapeHtml(entry.top_k)}</span>
                                <span class="mode-pill">hits=${escapeHtml(entry.hit_count)}</span>
                                <span class="mode-pill">latency_ms=${escapeHtml(entry.latency_ms)}</span>
                            </div>
                            <p class="meta external-search-activity-item-meta">
                                updated=${escapeHtml(formatExternalSearchTimestamp(entry.updated_at))}
                                ${entry.error_type ? ` | error=${escapeHtml(entry.error_type)}` : ""}
                            </p>
                        </article>
                    `;
                })
                .join("")}
        </div>
    `;
}

function renderExternalSearchWorkspace() {
    renderExternalSearchJsonDebug(externalSearchState.result);
    renderExternalSearchSession();
    renderExternalSearchResults();
    renderExternalSearchActions(externalSearchState.question);
}

function syncExternalSearchActionState() {
    const questionLength = getNormalizedExternalSearchValue().length;
    const isInputLocked = externalSearchInput instanceof HTMLTextAreaElement && externalSearchInput.disabled;
    const hasWorkspaceState = externalSearchState.status !== "idle";
    const canClear =
        (questionLength > 0 || hasWorkspaceState) &&
        !isInputLocked &&
        !isSearching;
    const canSubmit =
        questionLength >= minimumExternalSearchLength &&
        !isInputLocked &&
        !isSearching;

    if (externalSearchClearButton instanceof HTMLButtonElement) {
        externalSearchClearButton.disabled = !canClear;
        externalSearchClearButton.classList.toggle("is-active", canClear);
    }

    if (externalSearchSubmitButton instanceof HTMLButtonElement) {
        externalSearchSubmitButton.disabled = !canSubmit;
        externalSearchSubmitButton.classList.toggle("is-loading", isSearching);
        externalSearchSubmitButton.setAttribute(
            "aria-busy",
            isSearching ? "true" : "false",
        );
        externalSearchSubmitButton.title = isSearching
            ? "Пошук виконується"
            : "Надіслати запит";
    }
}

function setExternalSearchPendingState(nextValue) {
    isSearching = nextValue;

    if (externalSearchForm instanceof HTMLFormElement) {
        externalSearchForm.setAttribute("aria-busy", nextValue ? "true" : "false");
    }

    if (
        externalSearchInput instanceof HTMLTextAreaElement &&
        !externalSearchInput.disabled
    ) {
        externalSearchInput.readOnly = nextValue;
    }

    getExternalSearchTopKInputs().forEach((input) => {
        if (!input.disabled || nextValue === false) {
            const locked = input.dataset.locked === "true";
            input.disabled = locked ? true : nextValue;
        }
    });

    syncExternalSearchActionState();
}

function resetExternalSearchState() {
    externalSearchState.question = "";
    externalSearchState.topK = getSelectedExternalSearchTopK();
    externalSearchState.result = null;
    externalSearchState.error = "";
    externalSearchState.status = "idle";
    externalSearchState.latencyMs = null;
    externalSearchState.updatedAt = "";
    renderExternalSearchWorkspace();
}

async function refreshExternalSearchActivity(options = {}) {
    if (!externalSearchState.isAuthenticated) {
        renderExternalSearchActivity([], {
            error: "доступно тільки після admin authorization",
        });
        return [];
    }

    if (options.loading) {
        renderExternalSearchActivity([], { loading: true });
    }

    try {
        const response = await window.fetch(
            `/web-search-history?limit=${externalSearchActivityLimit}`,
            {
                headers: {
                    Accept: "application/json",
                },
                credentials: "same-origin",
            },
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        const entries = Array.isArray(payload.entries) ? payload.entries : [];
        renderExternalSearchActivity(entries);

        if (
            entries.length > 0 &&
            (externalSearchState.status === "success" || externalSearchState.status === "error")
        ) {
            externalSearchState.latencyMs = Number.isInteger(entries[0].latency_ms)
                ? entries[0].latency_ms
                : null;
            externalSearchState.updatedAt =
                typeof entries[0].updated_at === "string" ? entries[0].updated_at : "";
            renderExternalSearchSession();
        }

        return entries;
    } catch (error) {
        renderExternalSearchActivity([], {
            error: error instanceof Error ? error.message : "unknown error",
        });
        return [];
    }
}

async function submitExternalSearchWithFetch(questionValue) {
    const topKValue = getSelectedExternalSearchTopK();

    externalSearchState.question = questionValue;
    externalSearchState.topK = topKValue;
    externalSearchState.error = "";
    externalSearchState.result = null;
    externalSearchState.status = "loading";
    externalSearchState.latencyMs = null;
    externalSearchState.updatedAt = "";

    setExternalSearchPendingState(true);
    renderExternalSearchWorkspace();
    replaceUrlWithExternalSearchParams(questionValue, topKValue);

    try {
        const response = await window.fetch("/web-search", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },
            credentials: "same-origin",
            body: JSON.stringify({
                question: questionValue,
                top_k: topKValue,
            }),
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message =
                typeof payload.detail === "string" && payload.detail.trim()
                    ? payload.detail
                    : `Web search failed with status ${response.status}.`;
            throw new Error(message);
        }

        externalSearchState.result =
            payload && typeof payload === "object" ? payload : null;
        externalSearchState.error = "";
        externalSearchState.status = "success";
        renderExternalSearchWorkspace();
        focusExternalSearchResultsCard();

        if (externalSearchInput instanceof HTMLTextAreaElement) {
            externalSearchInput.value = "";
        }

        setExternalSearchPendingState(false);
        syncExternalSearchActionState();
        void refreshExternalSearchActivity({ loading: true });
    } catch (error) {
        externalSearchState.result = null;
        externalSearchState.error =
            error instanceof Error ? error.message : "Failed to fetch web search results.";
        externalSearchState.status = "error";
        renderExternalSearchWorkspace();
        setExternalSearchPendingState(false);
        syncExternalSearchActionState();
        void refreshExternalSearchActivity({ loading: true });
    } finally {
        if (isSearching) {
            setExternalSearchPendingState(false);
            syncExternalSearchActionState();
        }
    }
}

export function initializeExternalSearchPage() {
    if (!(externalSearchInput instanceof HTMLTextAreaElement)) {
        return;
    }

    getExternalSearchTopKInputs().forEach((input) => {
        input.dataset.locked = input.disabled ? "true" : "false";
    });

    parseExternalSearchInitialState();
    renderExternalSearchWorkspace();
    syncExternalSearchActionState();
    void refreshExternalSearchActivity({ loading: true });

    externalSearchInput.addEventListener("input", () => {
        syncExternalSearchActionState();
    });

    externalSearchClearButton?.addEventListener("click", () => {
        if (
            !(externalSearchClearButton instanceof HTMLButtonElement) ||
            externalSearchClearButton.disabled
        ) {
            return;
        }

        externalSearchInput.value = "";
        replaceUrlWithoutExternalSearchParams();
        resetExternalSearchState();
        syncExternalSearchActionState();
        externalSearchInput.focus();
    });

    externalSearchActionsContent?.addEventListener("click", (event) => {
        const target = event.target instanceof HTMLElement ? event.target : null;
        const nextQuery = target?.dataset.externalSearchFollowup ?? "";
        if (!nextQuery) {
            return;
        }

        externalSearchInput.value = nextQuery;
        syncExternalSearchActionState();
        externalSearchInput.focus();
        externalSearchInput.scrollIntoView({ behavior: "smooth", block: "center" });
    });

    getExternalSearchTopKInputs().forEach((input) => {
        input.addEventListener("change", () => {
            if (!getNormalizedExternalSearchValue()) {
                externalSearchState.topK = getSelectedExternalSearchTopK();
                renderExternalSearchSession();
            }
        });
    });

    if (!(externalSearchForm instanceof HTMLFormElement)) {
        return;
    }

    externalSearchForm.addEventListener("submit", (event) => {
        const questionValue = getNormalizedExternalSearchValue();
        if (questionValue.length < minimumExternalSearchLength || isSearching) {
            event.preventDefault();
            syncExternalSearchActionState();
            return;
        }

        if (typeof window.fetch !== "function") {
            return;
        }

        event.preventDefault();
        void submitExternalSearchWithFetch(questionValue);
    });
}
