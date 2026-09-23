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

function showToast(message, type = "info") {
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

    const remove = () => {
        toast.classList.add("toast-hide");
        toast.addEventListener("animationend", () => toast.remove(), { once: true });
    };

    toast.querySelector(".toast-close").addEventListener("click", remove);
    setTimeout(remove, TOAST_DURATION_MS);

    container.appendChild(toast);
}