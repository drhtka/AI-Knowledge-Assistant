const appI18nElement = document.getElementById("app-i18n");

let appI18n = {};

if (appI18nElement instanceof HTMLScriptElement) {
    try {
        const parsed = JSON.parse(appI18nElement.textContent || "{}");
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
            appI18n = parsed;
        }
    } catch {
        appI18n = {};
    }
}

function getNestedValue(container, dottedKey) {
    return dottedKey.split(".").reduce((current, part) => {
        if (current && typeof current === "object" && part in current) {
            return current[part];
        }
        return undefined;
    }, container);
}

export function t(key, replacements = {}) {
    const value = getNestedValue(appI18n, key);
    if (typeof value !== "string") {
        return key;
    }

    return value.replace(/\{(\w+)\}/g, (_, token) =>
        token in replacements ? String(replacements[token]) : `{${token}}`,
    );
}

export function getCurrentLocale() {
    const locale = getNestedValue(appI18n, "meta.locale");
    return typeof locale === "string" && locale ? locale : undefined;
}
