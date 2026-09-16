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