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

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".modal-overlay, .modal-overlay-centered").forEach((el) => {
        if (!el.classList.contains("open")) {
            el.style.display = "none";
        }
    });
});

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