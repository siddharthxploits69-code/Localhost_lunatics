# Vertity AI — Autonomous Pre-Publication Brand Governance Platform

> **Inkloom AI Hackathon — Round 3 Final Product Submission**  
> *Team LocalHost-Lunatics | SIES GST*  
> **Live Deployment:** [https://vertity-ai.onrender.com/](https://vertity-ai.onrender.com/)  
> **GitHub Repository:** [https://github.com/siddharthxploits69-code/Localhost_lunatics.git](https://github.com/siddharthxploits69-code/Localhost_lunatics.git)

---

## 🧭 Executive Summary

**Vertity AI** is an enterprise pre-publication governance platform that autonomously intercepts marketing collateral, visual banners, and promotional copy before it reaches public channels. By combining fast **deterministic rule evaluation** with **Google Gemini multimodal semantic analysis**, Vertity AI eliminates brand drift, prevents legal liability, and enforces statutory transparency.

Every detected issue provides an **intent-preserving minimal fix**, an exact citation to an approved brand policy document, and an immutable cryptographic audit trail.

---

## 🎯 1-Click Demo Personas for Judges

| Persona Role | Email / ID | Default Permissions & Main Workflow |
| :--- | :--- | :--- |
| **👑 Brand Admin** | `admin@vertity.ai` | Full access: edit Brand Rulebook, upload policy PDFs, view organizational analytics |
| **✍️ Agency Creator** | `creator@agency.com` | Creator Studio: audit drafts, inspect visual banners, 1-click accept fixes |
| **🔎 Enterprise Reviewer** | `reviewer@enterprise.com` | Review Cockpit: approve or reject drafts with editorial feedback notes |

*(Clicking the persona badges at the top of the live web app instantly switches active roles with zero login friction.)*

---

## 🚀 The Three Round 3 Commitments Delivered

### 1. Multimodal Visual Banner & WCAG 2.1 AA Accessibility Inspector (`/api/audit-visual`)
- **Pillow Pixel Quantization & Color Math:** Extracts exact dominant RGB/HEX palettes directly from raw image bytes and compares against approved brand tokens (`#6366F1`, `#0F172A`, `#06B6D4`).
- **W3C WCAG 2.1 AA Contrast Ratio:** Computes exact relative luminance \(L = 0.2126R + 0.7152G + 0.0722B\) to verify required **4.5:1 text-to-background contrast** for digital accessibility.
- **Multimodal Gemini Vision Inspection:** Scans uploaded banners for brand logo presence, visual text drift (OCR), auto-generated accessible alt-text, and visual region heatmaps.

### 2. Live Browser Extension & In-App CMS Copilot (`chrome_extension/`, `/api/audit-inline`)
- **Manifest V3 Extension Bundle:** Ready for 1-click download from `/api/extension/download` as a packaged ZIP bundle for Chrome and Edge Developer Mode.
- **Real-Time Inline Linting:** Non-persisting endpoint `/api/audit-inline` provides live red/amber underlines directly inside Google Docs, LinkedIn, and CMS editors.
- **Longest-Match Deduplication:** Advanced span matching prevents overlapping or duplicate badges, providing smooth 1-click in-place text replacement.
- **Live Built-in Simulator:** Judges can test the extension's behavior directly inside the web platform without installing external files.

### 3. Automated EU AI Act (Art. 50) Compliance & Cryptographic PDF Audit Receipts (`pdf_generator.py`, `/api/receipts`)
- **EU AI Act Regulation (EU) 2024/1689 Article 50:** Evaluates synthetic / generative AI marketing channels and verifies statutory transparency disclosures. Provides a **1-click statutory disclaimer injection** (`injectEUStatutoryDisclaimer`).
- **Zero-Dependency PDF 1.4 Generator:** Built using pure Python standard library (`io`, `zlib`, `hashlib`) with zero heavy dependencies (no ReportLab/WeasyPrint required), ensuring instant 50ms rendering and zero memory leaks.
- **Tamper-Proof Cryptographic Ledger:** Binds Submission ID, content SHA-256 digest, active Rulebook snapshot hash, and compliance score into a cryptographic seal verified via `/api/receipts/{receipt_hash}/verify`.

---

## 🏛️ Technical Architecture

```
[ Content Creator / Agency / CMS ]
            │
            ▼
┌────────────────────────────────────────────────────────┐
│            Vertity AI Pre-Publication Engine           │
│                                                        │
│  ┌──────────────────────┐    ┌──────────────────────┐  │
│  │  Deterministic Rule  │    │  Google Gemini 2.5   │  │
│  │  Matcher (Exact)     │    │  Flash Multimodal    │  │
│  └──────────┬───────────┘    └──────────┬───────────┘  │
│             │                           │              │
│             ▼                           ▼              │
│  ┌──────────────────────────────────────────────────┐  │
│  │   Hybrid Scoring & Intent-Preserving Fix Engine   │  │
│  └──────────────────────────┬───────────────────────┘  │
│                             │                          │
│  ┌──────────────────────────┴───────────────────────┐  │
│  │   EU AI Act Article 50 Statutory Validator       │  │
│  └──────────────────────────┬───────────────────────┘  │
│                             │                          │
│  ┌──────────────────────────┴───────────────────────┐  │
│  │   Cryptographic SHA-256 Ledger & PDF Generator   │  │
│  └──────────────────────────────────────────────────┘  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  Immutable SHA-256 PDF Audit Receipt  │
        │  W3C WCAG 2.1 AA Compliance Score     │
        │  Human-in-the-Loop Review Cockpit     │
        └───────────────────────────────────────┘
```

---

## 🧪 Automated Quality Verification Suite

Vertity AI includes a zero-dependency test suite verifying all 7 core endpoints:

```bash
python test_api.py
```

### Verified Test Cases:
1. `GET /api/health` — Verifies API health and runtime telemetry.
2. `GET /api/guidelines` — Verifies 9 grounded brand rules across all 5 drift pillars.
3. `POST /api/audit` — Verifies hybrid deterministic + semantic AI analysis.
4. `GET /api/analytics` — Verifies organizational drift intelligence aggregation.
5. `POST /api/audit-visual` — Verifies Pillow quantization, WCAG 4.5:1 luminance, and Gemini Vision.
6. `POST /api/audit-inline` & `GET /api/extension/download` — Verifies browser extension linting and ZIP packaging.
7. `GET /api/receipts/{sub_id}/pdf` & `GET /api/receipts/{hash}/verify` — Verifies cryptographic SHA-256 generation and ledger seal validation.

---

## 💻 Local Quickstart

### Prerequisites
- Python 3.10 or higher
- Git

### Installation Steps

```bash
# 1. Clone repository
git clone https://github.com/siddharthxploits69-code/Localhost_lunatics.git
cd Localhost_lunatics

# 2. Create virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install lightweight dependencies
pip install -r requirements.txt

# 4. Set Gemini API Key (optional, fallback deterministic rules always run)
export GEMINI_API_KEY="your-gemini-api-key"
# On Windows PowerShell:
$env:GEMINI_API_KEY="your-gemini-api-key"

# 5. Launch application
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open your browser at: **`http://localhost:8000`**

---

## 🗺️ Product Roadmap & Future Horizons

- [x] **Phase 1 (Round 2):** Core Hybrid Audit Engine, Knowledge Base RAG, Intent-Preserving Fixes, Review Cockpit.
- [x] **Phase 2 (Round 3):** Multimodal Visual & WCAG 2.1 AA Inspector, Browser Extension & CMS Copilot, EU AI Act Article 50 Compliance & Cryptographic PDF Receipts.
- [ ] **Phase 3 (Post-Hackathon Q1 2027):** Native Figma & Canva Plugin Integration for direct creative canvas linting.
- [ ] **Phase 4 (Q2 2027):** Multi-Language Brand Governance across 24 European and Asian languages.
- [ ] **Phase 5 (Q3 2027):** Automated Blockchain Anchor (Polygon/Ethereum) for public multi-enterprise regulatory verification.

---

## 👥 Team LocalHost-Lunatics — SIES GST
- **Project Name:** Vertity AI
- **Event:** Inkloom AI Hackathon Round 3
