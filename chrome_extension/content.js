/**
 * Vertity AI — Live Brand Governance Copilot (Content Script v3.0.0)
 * Real-time inline compliance linting, grounded citations, 1-click replacement,
 * and manager queue routing for Google Docs, LinkedIn, WordPress, Gmail, and CMS editors.
 */
(() => {
  if (window.__vertityExtInjected) return;
  window.__vertityExtInjected = true;

  const DEFAULT_BACKEND = "https://vertity-ai.onrender.com";
  let backendUrl = DEFAULT_BACKEND;
  let autoLintEnabled = true;
  let lastActiveTarget = null;
  let lastAuditedText = "";
  let debounceTimer = null;
  let drawerOpen = false;
  let latestResult = {
    overall_compliance_score: 100,
    status: "clean",
    summary: "Focus any text editor or composer to start live Vertity AI linting.",
    flagged_issues: [],
    platform: detectPlatform()
  };

  function detectPlatform() {
    const h = (window.location.hostname || "").toLowerCase();
    if (h.includes("docs.google.com")) return "Google Docs";
    if (h.includes("linkedin.com")) return "LinkedIn";
    if (h.includes("wordpress") || h.includes("wp-admin") || document.querySelector(".block-editor-page")) return "WordPress CMS";
    if (h.includes("mail.google.com")) return "Gmail";
    if (h.includes("notion.so")) return "Notion";
    if (h.includes("medium.com") || h.includes("substack.com")) return "Editorial CMS";
    if (h.includes("vertity-ai.onrender.com") || h === "127.0.0.1" || h === "localhost") return "Vertity Sandbox";
    return h || "Web Editor";
  }

  function loadSettings() {
    try {
      if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
        chrome.storage.sync.get(["vertityBackendUrl", "vertityAutoLint"], (res) => {
          if (res && res.vertityBackendUrl) backendUrl = res.vertityBackendUrl.replace(/\/+$/, "");
          if (res && typeof res.vertityAutoLint === "boolean") autoLintEnabled = res.vertityAutoLint;
        });
        chrome.storage.onChanged.addListener((changes) => {
          if (changes.vertityBackendUrl && changes.vertityBackendUrl.newValue) {
            backendUrl = changes.vertityBackendUrl.newValue.replace(/\/+$/, "");
          }
          if (changes.vertityAutoLint && typeof changes.vertityAutoLint.newValue === "boolean") {
            autoLintEnabled = changes.vertityAutoLint.newValue;
          }
        });
      }
    } catch (_) {
      // Fallback to default backend
    }
  }

  function isEditableElement(el) {
    if (!el || el.nodeType !== 1) return false;
    if (el.closest && el.closest("#vertity-ext-root")) return false;
    const tag = (el.tagName || "").toUpperCase();
    if (tag === "TEXTAREA") return !el.disabled && !el.readOnly;
    if (tag === "INPUT") {
      const t = (el.type || "text").toLowerCase();
      return ["text", "search", "email", "url"].includes(t) && !el.disabled && !el.readOnly;
    }
    if (el.isContentEditable) return true;
    if (el.getAttribute && el.getAttribute("role") === "textbox") return true;
    return false;
  }

  function findBestEditorTarget() {
    const active = document.activeElement;
    if (isEditableElement(active)) return active;
    if (lastActiveTarget && document.contains(lastActiveTarget)) return lastActiveTarget;

    // Look for prominent composers (LinkedIn, WordPress, CMS, standard forms)
    const candidates = Array.from(
      document.querySelectorAll('textarea, [contenteditable="true"], [role="textbox"]')
    ).filter((el) => {
      if (el.closest("#vertity-ext-root")) return false;
      const rect = el.getBoundingClientRect();
      return rect.width >= 120 && rect.height >= 28;
    });

    if (candidates.length === 0) return null;
    candidates.sort((a, b) => {
      const ra = a.getBoundingClientRect();
      const rb = b.getBoundingClientRect();
      return rb.width * rb.height - ra.width * ra.height;
    });
    return candidates[0];
  }

  function extractGoogleDocsText() {
    // Google Docs stores accessible paragraphs in DOM nodes or selection depending on canvas/DOM mode
    const nodes = document.querySelectorAll(".kix-paragraphrenderer, .kix-lineview-content, .kix-wordhtmlgenerator-word-node");
    if (nodes && nodes.length > 0) {
      const text = Array.from(nodes).map((n) => n.innerText || n.textContent || "").join("\n").trim();
      if (text.length > 0) return text;
    }
    const sel = window.getSelection ? window.getSelection().toString().trim() : "";
    if (sel.length > 0) return sel;
    return "";
  }

  function getEditorText(el) {
    if (detectPlatform() === "Google Docs") {
      const gText = extractGoogleDocsText();
      if (gText) return gText;
    }
    if (!el) {
      const sel = window.getSelection ? window.getSelection().toString().trim() : "";
      return sel;
    }
    const tag = (el.tagName || "").toUpperCase();
    if (tag === "TEXTAREA" || tag === "INPUT") {
      return el.value || "";
    }
    return (el.innerText || el.textContent || "").trim();
  }

  function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function buildSnippetRegex(snippet) {
    const startsWord = /^[A-Za-z0-9_]/.test(snippet);
    const endsWord = /[A-Za-z0-9_]$/.test(snippet);
    const pattern = `${startsWord ? "\\b" : ""}${escapeRegex(snippet)}${endsWord ? "\\b" : ""}`;
    return new RegExp(pattern, "i");
  }

  function replaceInContentEditable(rootEl, targetSnippet, replacement) {
    const regex = buildSnippetRegex(targetSnippet);
    const walker = document.createTreeWalker(rootEl, NodeFilter.SHOW_TEXT, null);
    let node;
    while ((node = walker.nextNode())) {
      const val = node.nodeValue || "";
      if (regex.test(val)) {
        node.nodeValue = val.replace(regex, replacement);
        return true;
      }
    }
    // Fallback if snippet spans multiple inline child nodes
    const fullText = rootEl.innerText || "";
    if (regex.test(fullText)) {
      rootEl.innerText = fullText.replace(regex, replacement);
      return true;
    }
    return false;
  }

  function setNativeInputValue(el, newValue) {
    const proto = el.tagName.toUpperCase() === "TEXTAREA"
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
    if (descriptor && descriptor.set) {
      descriptor.set.call(el, newValue);
    } else {
      el.value = newValue;
    }
  }

  function applyReplacementOnPage(snippet, replacement) {
    const target = findBestEditorTarget();
    if (!target) return { applied: false, reason: "No editable field active on page." };

    let applied = false;
    const regex = buildSnippetRegex(snippet);
    const tag = (target.tagName || "").toUpperCase();

    if (tag === "TEXTAREA" || tag === "INPUT") {
      const current = target.value || "";
      if (regex.test(current)) {
        const updated = current.replace(regex, replacement);
        setNativeInputValue(target, updated);
        applied = true;
      }
    } else if (target.isContentEditable || target.getAttribute("role") === "textbox") {
      applied = replaceInContentEditable(target, snippet, replacement);
    }

    if (applied) {
      try {
        target.dispatchEvent(new InputEvent("input", { bubbles: true, cancelable: true, data: replacement }));
      } catch (_) {
        target.dispatchEvent(new Event("input", { bubbles: true }));
      }
      target.dispatchEvent(new Event("change", { bubbles: true }));
      lastAuditedText = "";
      runInlineAudit(true, false);
    }

    return { applied };
  }

  function applyAllFixes() {
    const issues = latestResult.flagged_issues || [];
    let count = 0;
    for (const issue of issues) {
      const res = applyReplacementOnPage(issue.original_text_snippet, issue.suggested_correction);
      if (res.applied) count += 1;
    }
    return { fixedCount: count };
  }

  async function runInlineAudit(force = false, includeAi = false) {
    const target = findBestEditorTarget();
    if (target) lastActiveTarget = target;
    const text = getEditorText(target);
    const platform = detectPlatform();

    if (!text || text.trim().length < 4) {
      latestResult = {
        overall_compliance_score: 100,
        status: "clean",
        summary: platform === "Google Docs"
          ? "Highlight text in Google Docs (or type in any editor) and click Re-Scan."
          : "Type or focus any editor to run live Vertity AI linting.",
        flagged_issues: [],
        platform
      };
      renderUI();
      return latestResult;
    }

    if (!force && text === lastAuditedText) {
      return latestResult;
    }
    lastAuditedText = text;

    try {
      const resp = await fetch(`${backendUrl}/api/audit-inline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          page_url: window.location.href,
          page_title: document.title || "Web Draft",
          platform,
          include_ai: includeAi
        })
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      latestResult = {
        ...data,
        platform
      };
    } catch (err) {
      latestResult = {
        overall_compliance_score: latestResult.overall_compliance_score || 100,
        status: "offline",
        summary: `Could not reach Vertity API (${backendUrl}). Switch backend in extension popup.`,
        flagged_issues: latestResult.flagged_issues || [],
        platform
      };
    }

    renderUI();
    return latestResult;
  }

  async function submitToManagerQueue() {
    const target = findBestEditorTarget();
    const text = getEditorText(target);
    if (!text || text.trim().length < 4) {
      return { ok: false, error: "Editor is empty. Write or select draft text first." };
    }

    const platform = detectPlatform();
    const payload = {
      title: document.title ? `${platform}: ${document.title.slice(0, 60)}` : `${platform} Draft`,
      content_type: platform === "LinkedIn" ? "social_media" : "blog",
      channel_source: `${platform} Browser Extension`,
      creator_name: "Extension Copilot User",
      content_text: text
    };

    try {
      const resp = await fetch(`${backendUrl}/api/audit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      return { ok: true, submission_id: data.submission_id, score: data.overall_compliance_score };
    } catch (err) {
      return { ok: false, error: String(err) };
    }
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function injectUI() {
    if (document.getElementById("vertity-ext-root")) return;

    const root = document.createElement("div");
    root.id = "vertity-ext-root";
    root.innerHTML = `
      <div class="vertity-ext-drawer hidden" id="vertity-ext-drawer">
        <div class="vertity-ext-header">
          <div class="vertity-ext-brand">
            <div class="vertity-ext-logo-badge">V</div>
            <div>
              <div style="font-size:12px;font-weight:800;color:#fff;">Vertity AI Copilot</div>
              <div style="font-size:10px;color:#94a3b8;" id="vertity-ext-platform-label">Live Inline Governance</div>
            </div>
          </div>
          <button class="vertity-ext-close" id="vertity-ext-close-btn" title="Minimize">✕</button>
        </div>
        <div class="vertity-ext-meta">
          <span id="vertity-ext-summary-line">Ready to lint active editor</span>
          <span id="vertity-ext-score-chip" style="font-weight:800;color:#34d399;">100/100</span>
        </div>
        <div class="vertity-ext-body" id="vertity-ext-body"></div>
        <div class="vertity-ext-footer">
          <button class="vertity-ext-btn-secondary" id="vertity-ext-scan-btn" title="Run deep scan with Gemini AI">Deep Scan</button>
          <button class="vertity-ext-btn-secondary" id="vertity-ext-fixall-btn" title="Apply all 1-click fixes">Fix All</button>
          <button class="vertity-ext-btn-primary" id="vertity-ext-queue-btn">Route to Queue</button>
        </div>
      </div>

      <div class="vertity-ext-pill" id="vertity-ext-pill" title="Toggle Vertity AI Governance Copilot">
        <span class="vertity-ext-dot" id="vertity-ext-dot"></span>
        <span class="vertity-ext-pill-title">Vertity AI</span>
        <span class="vertity-ext-pill-score" id="vertity-ext-pill-score">100% · Clean</span>
      </div>
    `;

    document.body.appendChild(root);

    document.getElementById("vertity-ext-pill").addEventListener("click", () => {
      drawerOpen = !drawerOpen;
      document.getElementById("vertity-ext-drawer").classList.toggle("hidden", !drawerOpen);
      if (drawerOpen) runInlineAudit(true, false);
    });

    document.getElementById("vertity-ext-close-btn").addEventListener("click", () => {
      drawerOpen = false;
      document.getElementById("vertity-ext-drawer").classList.add("hidden");
    });

    document.getElementById("vertity-ext-scan-btn").addEventListener("click", async () => {
      const btn = document.getElementById("vertity-ext-scan-btn");
      btn.textContent = "Scanning...";
      await runInlineAudit(true, true);
      btn.textContent = "Deep Scan";
    });

    document.getElementById("vertity-ext-fixall-btn").addEventListener("click", () => {
      applyAllFixes();
    });

    document.getElementById("vertity-ext-queue-btn").addEventListener("click", async () => {
      const btn = document.getElementById("vertity-ext-queue-btn");
      btn.textContent = "Routing...";
      const res = await submitToManagerQueue();
      btn.textContent = res.ok ? `Queued (${res.submission_id})` : "Queue Failed";
      setTimeout(() => { btn.textContent = "Route to Queue"; }, 2800);
    });
  }

  function renderUI() {
    const dot = document.getElementById("vertity-ext-dot");
    const pillScore = document.getElementById("vertity-ext-pill-score");
    const platformLabel = document.getElementById("vertity-ext-platform-label");
    const summaryLine = document.getElementById("vertity-ext-summary-line");
    const scoreChip = document.getElementById("vertity-ext-score-chip");
    const body = document.getElementById("vertity-ext-body");
    if (!dot || !body) return;

    const score = typeof latestResult.overall_compliance_score === "number"
      ? latestResult.overall_compliance_score
      : 100;
    const issues = latestResult.flagged_issues || [];

    dot.classList.remove("warn", "danger");
    if (score < 65) dot.classList.add("danger");
    else if (score < 90 || issues.length > 0) dot.classList.add("warn");

    pillScore.textContent = issues.length > 0
      ? `${score}% · ${issues.length} Flag${issues.length > 1 ? "s" : ""}`
      : `${score}% · Clean`;

    platformLabel.textContent = `Platform: ${latestResult.platform || detectPlatform()}`;
    summaryLine.textContent = issues.length > 0
      ? `${issues.length} grounded issue${issues.length > 1 ? "s" : ""} found`
      : (latestResult.summary || "Zero drift detected");
    scoreChip.textContent = `${score}/100`;
    scoreChip.style.color = score >= 85 ? "#34d399" : (score >= 60 ? "#fbbf24" : "#f87171");

    if (issues.length === 0) {
      body.innerHTML = `
        <div class="vertity-ext-card" style="border-color: rgba(16, 185, 129, 0.35);">
          <div style="font-size:12px;font-weight:700;color:#34d399;">✓ Compliant Draft</div>
          <div class="vertity-ext-exp">${escapeHtml(latestResult.summary || "All terminology, pricing facts, and legal claims match your Brand Rulebook.")}</div>
        </div>
      `;
      return;
    }

    body.innerHTML = issues.map((issue, idx) => {
      const sevClass = issue.severity === "high" ? "vertity-ext-sev-high" : "vertity-ext-sev-med";
      return `
        <div class="vertity-ext-card">
          <div class="vertity-ext-card-top">
            <span class="vertity-ext-cat">${escapeHtml(issue.category)}</span>
            <span class="${sevClass}">${escapeHtml(issue.severity)}</span>
          </div>
          <div class="vertity-ext-cite">Proof: ${escapeHtml(issue.source_citation || "Brand Rulebook")}</div>
          <div class="vertity-ext-exp">${escapeHtml(issue.explanation)}</div>
          <div class="vertity-ext-fix-row">
            <div style="overflow:hidden;text-overflow:ellipsis;">
              <span class="vertity-ext-bad">${escapeHtml(issue.original_text_snippet)}</span>
              <span style="color:#64748b;margin:0 4px;">→</span>
              <span class="vertity-ext-good">${escapeHtml(issue.suggested_correction)}</span>
            </div>
            <button class="vertity-ext-btn-fix" data-fix-idx="${idx}">1-Click Fix</button>
          </div>
        </div>
      `;
    }).join("");

    body.querySelectorAll(".vertity-ext-btn-fix").forEach((btn) => {
      btn.addEventListener("click", () => {
        const i = Number(btn.getAttribute("data-fix-idx"));
        const targetIssue = issues[i];
        if (!targetIssue) return;
        const result = applyReplacementOnPage(
          targetIssue.original_text_snippet,
          targetIssue.suggested_correction
        );
        if (!result.applied) {
          btn.textContent = "Select Field";
        }
      });
    });
  }

  function scheduleLint(ev) {
    if (ev && ev.target && isEditableElement(ev.target)) {
      lastActiveTarget = ev.target;
    }
    if (!autoLintEnabled) return;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      runInlineAudit(false, false);
    }, 600);
  }

  function bindListeners() {
    document.addEventListener("focusin", scheduleLint, true);
    document.addEventListener("input", scheduleLint, true);
    document.addEventListener("keyup", scheduleLint, true);

    try {
      if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
        chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
          if (!msg || !msg.type) return;
          if (msg.type === "GET_STATE") {
            sendResponse({ state: latestResult });
            return false;
          }
          if (msg.type === "SCAN_PAGE") {
            runInlineAudit(true, Boolean(msg.includeAi)).then((state) => {
              sendResponse({ state });
            });
            return true;
          }
          if (msg.type === "APPLY_FIX") {
            const res = applyReplacementOnPage(msg.snippet, msg.replacement);
            setTimeout(() => {
              sendResponse({ applied: res.applied, state: latestResult });
            }, 350);
            return true;
          }
          if (msg.type === "FIX_ALL") {
            const res = applyAllFixes();
            setTimeout(() => {
              sendResponse({ ...res, state: latestResult });
            }, 350);
            return true;
          }
          if (msg.type === "SUBMIT_QUEUE") {
            submitToManagerQueue().then((res) => sendResponse(res));
            return true;
          }
          if (msg.type === "OPEN_DRAWER") {
            drawerOpen = true;
            const d = document.getElementById("vertity-ext-drawer");
            if (d) d.classList.remove("hidden");
            runInlineAudit(true, false).then((state) => sendResponse({ state }));
            return true;
          }
        });
      }
    } catch (_) {
      // Ignore if outside extension runtime
    }
  }

  loadSettings();
  injectUI();
  bindListeners();
  renderUI();
})();
