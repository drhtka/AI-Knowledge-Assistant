export function initializeCustomSelects(rootSelector) {
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

export function initializeAllCustomSelects() {
    initializeCustomSelects(".ask-settings-row-in-composer .custom-select");
    initializeCustomSelects(".system-runtime-form-row .custom-select");
    initializeCustomSelects(".chunking-custom-form-row .custom-select");
}
