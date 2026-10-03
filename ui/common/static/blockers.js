(function () {
    function tr(key, fallback) {
        try {
            return (typeof I18N !== "undefined" && I18N[key]) || fallback;
        } catch (error) {
            return fallback;
        }
    }

    function esc(value) {
        return String(value === null || value === undefined ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function shortName(blocker) {
        const name = (blocker.name || "").trim();
        if (name) return name;
        const text = (blocker.text || "").trim();
        if (text) return text.length > 30 ? text.slice(0, 30) + "…" : text;
        return "#" + blocker.number;
    }

    function tipItemHtml(blocker) {
        let html = `<div class="bk-tip-item"><div class="bk-tip-title">${esc(blocker.number)} · ${esc(shortName(blocker))}</div>`;
        if (blocker.text) {
            html += `<div class="bk-tip-label">${esc(tr("blocker_rule_label", "Your rule"))}</div><div class="bk-tip-text">${esc(blocker.text)}</div>`;
        }
        if (blocker.quote) {
            html += `<div class="bk-tip-label">${esc(tr("blocker_quote_label", "Posting says"))}</div><div class="bk-tip-quote">«${esc(blocker.quote)}»</div>`;
        }
        return html + "</div>";
    }

    function renderBlockerStrip(blockers) {
        const list = blockers || [];
        if (!list.length) return "";
        const visible = list.slice(0, 2);
        const rest = list.slice(2);
        let html = visible
            .map(
                (blocker) =>
                    `<span class="bk-pill" tabindex="0" data-tip="${esc(tipItemHtml(blocker))}"><span class="bk-pill-num">${esc(blocker.number)}</span><span class="bk-pill-name">${esc(shortName(blocker))}</span></span>`
            )
            .join("");
        if (rest.length) {
            html += `<span class="bk-pill more" tabindex="0" data-tip="${esc(rest.map(tipItemHtml).join(""))}">+${rest.length}</span>`;
        }
        return html;
    }

    function renderBlockerDetails(blockers) {
        const list = blockers || [];
        if (!list.length) return "";
        const cards = list
            .map((blocker) => {
                let body = "";
                if (blocker.text) {
                    body += `<div class="bk-card-label">${esc(tr("blocker_rule_label", "Your rule"))}</div><div class="bk-card-text">${esc(blocker.text)}</div>`;
                }
                if (blocker.quote) {
                    body += `<div class="bk-card-label">${esc(tr("blocker_quote_label", "Posting says"))}</div><div class="bk-card-quote">«${esc(blocker.quote)}»</div>`;
                }
                const details = body
                    ? `<details><summary>${esc(tr("blocker_details_toggle", "Rule and evidence"))}</summary>${body}</details>`
                    : "";
                return `<div class="bk-card"><span class="bk-pill-num bk-card-num">${esc(blocker.number)}</span><div class="bk-card-body"><div class="bk-card-name">${esc(shortName(blocker))}</div>${details}</div></div>`;
            })
            .join("");
        return `<div class="bk-panel"><div class="bk-panel-head"><span class="bk-panel-title">🚫 ${esc(tr("blockers_triggered_title", "Blockers triggered"))}</span><span class="bk-panel-count">${list.length}</span></div><p class="bk-panel-note">${esc(tr("blockers_score_note", ""))}</p>${cards}</div>`;
    }

    function hydrateBlockers(root) {
        (root || document).querySelectorAll("[data-blockers]").forEach((element) => {
            let list = [];
            try {
                list = JSON.parse(element.dataset.blockers || "[]");
            } catch (error) {
                list = [];
            }
            element.innerHTML = element.classList.contains("bk-detail-host")
                ? renderBlockerDetails(list)
                : renderBlockerStrip(list);
        });
    }

    let tipEl = null;

    function getTip() {
        if (!tipEl) {
            tipEl = document.createElement("div");
            tipEl.id = "bk-tip";
            document.body.appendChild(tipEl);
        }
        return tipEl;
    }

    function showTip(pill) {
        const tip = getTip();
        tip.innerHTML = pill.dataset.tip || "";
        tip.style.display = "block";
        tip.style.visibility = "hidden";
        const rect = pill.getBoundingClientRect();
        const tipRect = tip.getBoundingClientRect();
        const margin = 8;
        let left = Math.min(Math.max(margin, rect.left), window.innerWidth - tipRect.width - margin);
        let top = rect.bottom + 8;
        if (top + tipRect.height > window.innerHeight - margin) {
            top = Math.max(margin, rect.top - tipRect.height - 8);
        }
        tip.style.left = `${left}px`;
        tip.style.top = `${top}px`;
        tip.style.visibility = "visible";
    }

    function hideTip() {
        if (tipEl) tipEl.style.display = "none";
    }

    document.addEventListener("mouseover", (event) => {
        const pill = event.target.closest && event.target.closest(".bk-pill");
        if (pill) showTip(pill);
    });
    document.addEventListener("mouseout", (event) => {
        if (event.target.closest && event.target.closest(".bk-pill")) hideTip();
    });
    document.addEventListener("focusin", (event) => {
        const pill = event.target.closest && event.target.closest(".bk-pill");
        if (pill) showTip(pill);
    });
    document.addEventListener("focusout", (event) => {
        if (event.target.closest && event.target.closest(".bk-pill")) hideTip();
    });
    document.addEventListener("scroll", hideTip, true);
    document.addEventListener(
        "click",
        (event) => {
            if (event.target.closest && event.target.closest(".bk-pill")) event.stopPropagation();
        },
        true
    );
    document.addEventListener("DOMContentLoaded", () => hydrateBlockers(document));

    window.renderBlockerStrip = renderBlockerStrip;
    window.renderBlockerDetails = renderBlockerDetails;
    window.hydrateBlockers = hydrateBlockers;
})();