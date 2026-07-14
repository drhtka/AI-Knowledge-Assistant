import {
    askResultContent,
    askResultJsonContent,
    modeComparisonContent,
    questionClearButton,
    questionForm,
    searchResultContent,
    searchResultJsonContent,
    clearFormButton,
} from "../dom/elements.js";
import { escapeHtml } from "../shared/utils.js";

function renderJsonDebugContent(target, payload) {
    if (!(target instanceof HTMLElement)) {
        return;
    }

    target.textContent = JSON.stringify(payload ?? {}, null, 2);
}

export function getQuestionInput() {
    if (!(questionForm instanceof HTMLFormElement)) {
        return null;
    }

    const questionInput = questionForm.elements.namedItem("question");
    return questionInput instanceof HTMLInputElement || questionInput instanceof HTMLTextAreaElement
        ? questionInput
        : null;
}

export function getQuestionSubmitButton() {
    if (!(questionForm instanceof HTMLFormElement)) {
        return null;
    }

    const submitButton = questionForm.querySelector('button[type="submit"]');
    return submitButton instanceof HTMLButtonElement ? submitButton : null;
}

export function getQuestionClearButton() {
    return questionClearButton instanceof HTMLButtonElement
        ? questionClearButton
        : clearFormButton instanceof HTMLButtonElement
          ? clearFormButton
          : null;
}

export function getNormalizedQuestionValue() {
    const questionInput = getQuestionInput();
    return questionInput instanceof HTMLInputElement || questionInput instanceof HTMLTextAreaElement
        ? questionInput.value.trim()
        : "";
}

export function hasQuestionResultState() {
    const currentUrl = new URL(window.location.href);
    return currentUrl.searchParams.has("question");
}

export function syncQuestionActionState() {
    const hasQuestionValue = Boolean(getNormalizedQuestionValue());
    const submitButton = getQuestionSubmitButton();
    const clearButton = getQuestionClearButton();
    const hasResultState = hasQuestionResultState();
    const canClear = hasQuestionValue || hasResultState;

    if (submitButton instanceof HTMLButtonElement) {
        submitButton.disabled = !hasQuestionValue;
    }

    if (clearButton instanceof HTMLButtonElement) {
        clearButton.disabled = !canClear;
        clearButton.classList.toggle("is-active", canClear);
    }
}

export function replaceUrlWithoutQuestionParams() {
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.delete("question");
    nextUrl.searchParams.delete("top_k");
    nextUrl.searchParams.delete("retrieval_mode");
    nextUrl.searchParams.delete("web_question");
    nextUrl.searchParams.delete("web_top_k");
    window.history.replaceState({}, "", nextUrl.pathname + nextUrl.search);
}

export function replaceUrlWithQuestionParams(questionValue, retrievalModeValue, topKValue) {
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set("question", questionValue);
    nextUrl.searchParams.set("retrieval_mode", retrievalModeValue);
    nextUrl.searchParams.set("top_k", topKValue);
    nextUrl.searchParams.delete("web_question");
    nextUrl.searchParams.delete("web_top_k");
    window.history.replaceState({}, "", nextUrl.pathname + nextUrl.search);
}

export function renderAskResultContent(payload) {
    renderJsonDebugContent(askResultJsonContent, payload);

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
        <div class="chat-single-response">
            <div class="chat-single-response-head">
                <div class="chat-single-response-identity">
                    <span class="chat-single-response-avatar">A</span>
                    <div class="chat-single-response-meta-group">
                        <p class="chat-single-response-name">Assistant</p>
                        <p class="meta chat-single-response-meta">Single-turn grounded answer</p>
                    </div>
                </div>
            </div>
            <div class="pill-row answer-metric-row">
                <span class="mode-pill answer-metric-pill">
                    <span class="answer-metric-label">Confidence</span>
                    <strong>${escapeHtml(payload.confidence)}</strong>
                </span>
                <span class="mode-pill answer-metric-pill">
                    <span class="answer-metric-label">Latency</span>
                    <strong>${escapeHtml(payload.latency_ms)} ms</strong>
                </span>
                <span class="mode-pill answer-metric-pill">
                    <span class="answer-metric-label">Answer mode</span>
                    <strong>${escapeHtml(payload.answer_mode)}</strong>
                </span>
                <span class="mode-pill answer-metric-pill">
                    <span class="answer-metric-label">Retrieval</span>
                    <strong>${escapeHtml(payload.retrieval_mode)}</strong>
                </span>
            </div>
            <div class="chat-single-response-bubble">
                <p class="chat-single-response-text">${escapeHtml(payload.answer)}</p>
            </div>
            <div class="chat-single-response-sources">
                <p class="chat-single-response-sources-title">Sources</p>
                <ul class="list-reset chat-single-response-sources-list">${sourcesMarkup}</ul>
            </div>
        </div>
    `;
}

export function renderSearchResultContent(payload) {
    renderJsonDebugContent(searchResultJsonContent, payload);

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
                <article class="search-context-card">
                    <div class="search-context-card-head">
                        <div>
                            <p class="meta search-context-card-kicker">Retrieved source</p>
                            <h3 class="search-context-card-title">${escapeHtml(hit.title)}</h3>
                        </div>
                        <span class="mode-pill search-context-score-pill">${escapeHtml(hit.score)}</span>
                    </div>
                    <div class="pill-row search-context-meta-row">
                        <span class="mode-pill search-context-meta-pill">
                            <span class="search-context-meta-label">File</span>
                            <strong>${escapeHtml(hit.source_name)}</strong>
                        </span>
                        <span class="mode-pill search-context-meta-pill">
                            <span class="search-context-meta-label">Chunk</span>
                            <strong>${escapeHtml(hit.chunk_index)}</strong>
                        </span>
                        <span class="mode-pill search-context-meta-pill">
                            <span class="search-context-meta-label">Type</span>
                            <strong>${escapeHtml(hit.file_type)}</strong>
                        </span>
                    </div>
                    <p class="search-context-snippet">${escapeHtml(hit.snippet)}</p>
                </article>
            `,
        )
        .join("");

    searchResultContent.innerHTML = `
        <div class="pill-row context-summary-row">
            <span class="mode-pill context-summary-pill">
                <span class="context-summary-label">Search mode</span>
                <strong>${escapeHtml(payload.retrieval_mode)}</strong>
            </span>
            <span class="mode-pill context-summary-pill">
                <span class="context-summary-label">Hits</span>
                <strong>${escapeHtml(payload.hits.length)}</strong>
            </span>
        </div>
        <div class="search-context-grid">${hitsMarkup}</div>
    `;
}

export function renderModeComparisonContent(payload) {
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

    const sharedTopSource =
        items.length > 0 && items.every((item) => item.top_source === items[0].top_source)
            ? items[0].top_source
            : "";

    const itemsMarkup = items
        .map(
            (item) => `
                <div class="mode-compare-card">
                    <h3>${escapeHtml(item.mode)}</h3>
                    <div class="pill-row mode-compare-pill-row">
                        <span class="mode-pill mode-compare-pill">
                            <span class="mode-compare-pill-label">Top score</span>
                            <strong>${escapeHtml(item.top_score)}</strong>
                        </span>
                        <span class="mode-pill mode-compare-pill">
                            <span class="mode-compare-pill-label">Hits</span>
                            <strong>${escapeHtml(item.hit_count)}</strong>
                        </span>
                    </div>
                    ${
                        sharedTopSource
                            ? ""
                            : `
                    <p class="meta mode-compare-source-label">Top source</p>
                    <p class="mode-compare-source-value">${escapeHtml(item.top_source)}</p>
                    `
                    }
                </div>
            `,
        )
        .join("");

    modeComparisonContent.innerHTML = `
        ${
            sharedTopSource
                ? `
            <div class="mode-compare-shared-source">
                <p class="meta mode-compare-shared-source-label">Shared top source across modes</p>
                <strong class="mode-compare-shared-source-value">${escapeHtml(sharedTopSource)}</strong>
            </div>
        `
                : ""
        }
        <div class="mode-compare-grid">${itemsMarkup}</div>
    `;
}

export function renderQuestionLoadingState() {
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

export function resetQuestionResultState() {
    renderAskResultContent(null);
    renderSearchResultContent(null);
    renderModeComparisonContent(null);
}

export function clearQuestionInputAndState() {
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
}

export function fillQuestionInput(questionText) {
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

export async function submitQuestionWithFetch(questionValue) {
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
