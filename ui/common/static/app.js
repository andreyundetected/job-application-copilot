async function submitFormAjax(form, onSuccess) {
    const formData = new FormData(form);
    const response = await fetch(form.action, {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        alert("Something went wrong, please try again.");
        return;
    }

    const data = await response.json();
    onSuccess(data);
}

function bindAjaxForm(formId, onSuccess) {
    const form = document.getElementById(formId);
    if (!form) {
        return;
    }
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        await submitFormAjax(form, onSuccess);
    });
}

async function pollTaskStatus(taskIds, onUpdate, intervalMs = 2000) {
    const poll = async () => {
        const response = await fetch(`/api/tasks/status?ids=${taskIds.join(",")}`);
        const data = await response.json();
        onUpdate(data.tasks);

        const stillRunning = data.tasks.some(
            (task) => task.status === "pending" || task.status === "processing"
        );
        if (stillRunning) {
            setTimeout(poll, intervalMs);
        }
    };
    poll();
}

function initCustomSelect(root, onChange) {
    const trigger = root.querySelector(".custom-select-trigger");
    const label = root.querySelector("[data-select-label]");
    const options = [...root.querySelectorAll(".custom-select-option")];

    function closeAll() {
        document.querySelectorAll(".custom-select.open").forEach((el) => el.classList.remove("open"));
    }

    trigger.addEventListener("click", (event) => {
        event.stopPropagation();
        const wasOpen = root.classList.contains("open");
        closeAll();
        if (!wasOpen) root.classList.add("open");
    });

    options.forEach((option) => {
        option.addEventListener("click", () => {
            options.forEach((o) => o.classList.remove("selected"));
            option.classList.add("selected");
            if (label) label.textContent = option.dataset.label || option.textContent.trim();
            root.classList.remove("open");
            onChange(option.dataset.value, option);
        });
    });

    document.addEventListener("click", (event) => {
        if (!root.contains(event.target)) root.classList.remove("open");
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") root.classList.remove("open");
    });
}

function fmtPickerHtml(value, formats, up) {
    const check = '<svg class="custom-select-option-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
    const chevron = '<svg class="custom-select-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>';
    const options = formats
        .map((format) => `<button type="button" class="custom-select-option${format === value ? " selected" : ""}" data-value="${format}"><span>${format.toUpperCase()}</span>${check}</button>`)
        .join("");
    return `<div class="custom-select fmt-pick${up ? " up" : ""}" data-value="${value}"><button type="button" class="custom-select-trigger"><span data-select-label>${value.toUpperCase()}</span>${chevron}</button><div class="custom-select-menu">${options}</div></div>`;
}

document.addEventListener("click", (event) => {
    const picker = event.target.closest(".fmt-pick");
    document.querySelectorAll(".fmt-pick.open").forEach((el) => {
        if (el !== picker) el.classList.remove("open");
    });
    if (!picker) return;

    const option = event.target.closest(".custom-select-option");
    if (option) {
        const value = option.dataset.value;
        picker.dataset.value = value;
        picker.querySelectorAll(".custom-select-option").forEach((el) => el.classList.toggle("selected", el === option));
        picker.querySelector("[data-select-label]").textContent = value.toUpperCase();
        picker.classList.remove("open");
        picker.dispatchEvent(new CustomEvent("fmtchange", { detail: value }));
        return;
    }

    if (event.target.closest(".custom-select-trigger")) picker.classList.toggle("open");
});

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") document.querySelectorAll(".fmt-pick.open").forEach((el) => el.classList.remove("open"));
});

function flashSaved(el) {
    el.classList.add("visible");
    clearTimeout(el._hideTimeout);
    el._hideTimeout = setTimeout(() => el.classList.remove("visible"), 1600);
}

const TOAST_CONTAINER_ID = "toast-container";
const TOAST_MAX_VISIBLE = 3;
const TOAST_DURATION_MS = 10000;

function _getToastContainer() {
    let container = document.getElementById(TOAST_CONTAINER_ID);
    if (!container) {
        container = document.createElement("div");
        container.id = TOAST_CONTAINER_ID;
        container.className = "toast-container";
        document.body.appendChild(container);
    }
    return container;
}

const TOAST_PREFS_STORAGE_KEY = "toast_prefs";

function _toastEnabled(key) {
    if (!key) return true;
    try {
        const prefs = JSON.parse(localStorage.getItem(TOAST_PREFS_STORAGE_KEY) || "{}");
        return prefs[key] !== false;
    } catch (error) {
        return true;
    }
}

function showToast(message, type = "info", options = {}) {
    if (!_toastEnabled(options.key)) return;
    const container = _getToastContainer();

    while (container.children.length >= TOAST_MAX_VISIBLE) {
        container.removeChild(container.firstElementChild);
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-message"></span>
        <button type="button" class="toast-close">&times;</button>
    `;
    toast.querySelector(".toast-message").textContent = message;

    if (options.href) {
        toast.classList.add("toast-clickable");
        toast.querySelector(".toast-message").addEventListener("click", () => {
            window.location.href = options.href;
        });
    }

    const remove = () => {
        toast.classList.add("toast-hide");
        toast.addEventListener("animationend", () => toast.remove(), { once: true });
    };

    toast.querySelector(".toast-close").addEventListener("click", remove);
    setTimeout(remove, TOAST_DURATION_MS);

    container.appendChild(toast);
}