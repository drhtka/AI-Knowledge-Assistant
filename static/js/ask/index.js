import {
    askResultContent,
    modeComparisonContent,
    questionClearButton,
    questionForm,
    searchResultContent,
    clearFormButton,
} from "../dom/elements.js";
import { escapeHtml } from "../shared/utils.js";

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

export function syncQuestionActionState() {
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

export function renderSearchResultContent(payload) {
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
