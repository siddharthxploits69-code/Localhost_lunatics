const DEFAULT_BACKEND = "https://vertity-ai.onrender.com";

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function getActiveTab(callback) {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    callback(tabs && tabs[0] ? tabs[0] : null);
  });
}

function sendTabMessage(tabId, message, callback) {
  try {
    chrome.tabs.sendMessage(tabId, message, (resp) => {
      if (chrome.runtime.lastError) {
        callback(null, chrome.runtime.lastError.message);
      } else {
        callback(resp, null);
      }
    });
  } catch (err) {
    callback(null, String(err));
  }
}

function renderState(state) {
  const platformEl = document.getElementById("popup-platform");
  const scoreEl = document.getElementById("popup-score");
  const bodyEl = document.getElementById("popup-body");

  if (!state) {
    platformEl.textContent = "Reload tab or focus a web editor";
    bodyEl.innerHTML = `<div class="status-banner">Open Google Docs, LinkedIn, WordPress, or any CMS page and click <strong>Scan Active Editor</strong>.</div>`;
    return;
  }

  const score = typeof state.overall_compliance_score === "number" ? state.overall_compliance_score : 100;
  const issues = state.flagged_issues || [];
  platformEl.textContent = `Platform: ${state.platform || "Web Editor"}`;

  scoreEl.textContent = `${score}/100`;
  scoreEl.classList.remove("warn", "danger");
  if (score < 65) scoreEl.classList.add("danger");
  else if (score < 90 || issues.length > 0) scoreEl.classList.add("warn");

  if (issues.length === 0) {
    bodyEl.innerHTML = `
      <div class="card" style="border-color: rgba(16,185,129,0.4);">
        <div style="color:#34d399;font-weight:700;">✓ Clean — Zero Violations Detected</div>
        <div class="exp">${escapeHtml(state.summary || "Your active draft complies with grounded Vertity AI guidelines.")}</div>
      </div>
    `;
    return;
  }

  bodyEl.innerHTML = issues.map((issue, idx) => `
    <div class="card">
      <div class="card-top">
        <span class="cat">${escapeHtml(issue.category)}</span>
        <span class="${issue.severity === "high" ? "sev-high" : "sev-medium"}">${escapeHtml(issue.severity)}</span>
      </div>
      <div class="cite">Citation: ${escapeHtml(issue.source_citation || "Brand Rulebook")}</div>
      <div class="exp">${escapeHtml(issue.explanation)}</div>
      <div class="fix-box">
        <div style="overflow:hidden;text-overflow:ellipsis;">
          <span class="bad">${escapeHtml(issue.original_text_snippet)}</span>
          <span style="color:#64748b;margin:0 4px;">→</span>
          <span class="good">${escapeHtml(issue.suggested_correction)}</span>
        </div>
        <button class="btn-green popup-fix-btn" data-idx="${idx}">Fix</button>
      </div>
    </div>
  `).join("");

  bodyEl.querySelectorAll(".popup-fix-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.getAttribute("data-idx"));
      const item = issues[idx];
      if (!item) return;
      getActiveTab((tab) => {
        if (!tab) return;
        sendTabMessage(tab.id, {
          type: "APPLY_FIX",
          snippet: item.original_text_snippet,
          replacement: item.suggested_correction
        }, (resp) => {
          if (resp && resp.state) renderState(resp.state);
        });
      });
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const backendSelect = document.getElementById("backend-select");
  const autolintToggle = document.getElementById("autolint-toggle");
  const statusMsg = document.getElementById("popup-status-msg");

  chrome.storage.sync.get(["vertityBackendUrl", "vertityAutoLint"], (res) => {
    if (res && res.vertityBackendUrl) backendSelect.value = res.vertityBackendUrl;
    if (res && typeof res.vertityAutoLint === "boolean") autolintToggle.checked = res.vertityAutoLint;
  });

  backendSelect.addEventListener("change", () => {
    chrome.storage.sync.set({ vertityBackendUrl: backendSelect.value });
    statusMsg.textContent = "Backend updated";
  });

  autolintToggle.addEventListener("change", () => {
    chrome.storage.sync.set({ vertityAutoLint: autolintToggle.checked });
    statusMsg.textContent = autolintToggle.checked ? "Auto-Lint ON" : "Auto-Lint PAUSED";
  });

  document.getElementById("open-dashboard-link").addEventListener("click", (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: backendSelect.value || DEFAULT_BACKEND });
  });

  getActiveTab((tab) => {
    if (!tab) return renderState(null);
    sendTabMessage(tab.id, { type: "SCAN_PAGE", includeAi: false }, (resp, err) => {
      if (err || !resp) return renderState(null);
      renderState(resp.state);
    });
  });

  document.getElementById("btn-scan").addEventListener("click", () => {
    statusMsg.textContent = "Deep scanning active draft...";
    getActiveTab((tab) => {
      if (!tab) return;
      sendTabMessage(tab.id, { type: "SCAN_PAGE", includeAi: true }, (resp) => {
        statusMsg.textContent = "Deep scan complete";
        if (resp && resp.state) renderState(resp.state);
      });
    });
  });

  document.getElementById("btn-fix-all").addEventListener("click", () => {
    getActiveTab((tab) => {
      if (!tab) return;
      sendTabMessage(tab.id, { type: "FIX_ALL" }, (resp) => {
        if (resp) {
          statusMsg.textContent = `Applied ${resp.fixedCount || 0} fix(es)`;
          if (resp.state) renderState(resp.state);
        }
      });
    });
  });

  document.getElementById("btn-queue").addEventListener("click", () => {
    statusMsg.textContent = "Routing to Review Cockpit...";
    getActiveTab((tab) => {
      if (!tab) return;
      sendTabMessage(tab.id, { type: "SUBMIT_QUEUE" }, (resp) => {
        if (resp && resp.ok) {
          statusMsg.textContent = `Submitted as ${resp.submission_id}!`;
        } else {
          statusMsg.textContent = (resp && resp.error) ? resp.error : "Route failed";
        }
      });
    });
  });
});
