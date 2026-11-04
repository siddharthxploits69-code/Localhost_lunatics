# Vertity AI — Autonomous Pre-Publication Brand Governance Platform

> **Inkloom AI Hackathon Submission**  
> *Prevent brand drift before content goes live.*

Vertity AI reviews content against a company's brand knowledge base using deterministic rules and semantic LLM analysis. For every issue found, it explains the problem, cites the exact guideline or approved fact, and suggests an intent-preserving fix while humans maintain the final say.

---

## 🚀 Live Demo & Access
- **Web Platform:** [Deploy on Render or your cloud provider]
- **API Docs (Swagger UI):** `/docs`
- **Health Endpoint:** `/api/health`

---

## 🌟 The 5 Brand Drift Pillars Addressed
1. **Outdated Facts:** Stale pricing, discontinued features, incorrect statistics.
2. **Unsupported Claims:** Unverified superlatives (`best`, `#1`, `guaranteed 100% bug-free`) without legal substantiation.
3. **Tone & Terminology:** Inconsistent vocabulary (e.g. `clients` vs approved `Growth Partners`).
4. **Visual Compliance:** Palette validation, hex color adherence, logo presence.
5. **Accessibility Standards:** Contrast ratio validation (WCAG 2.1 AA 4.5:1), missing alt-text warnings.

---

## 🧠 Core Design Principles
- **Grounded, Not Guessing:** Findings cite uploaded sources (Brand Rulebook / Fact Sheet). Ungrounded advice is marked as a low-confidence suggestion.
- **Hybrid Checks:** Exact terms and numbers are verified deterministically; tone and semantic nuance are analyzed via LLM.
- **Intent-Preserving Rewrites:** Minimal edits that preserve the author's original voice and message.
- **Human in Control:** AI suggests; admins and reviewers accept, edit, or reject.
- **Governance Insights Engine:** Aggregates repeated organizational drift patterns to help refine brand guidelines over time.

---

## 🛠️ Tech Stack
- **Backend:** FastAPI, Python 3.10+, Uvicorn, Pydantic v2
- **AI Engine:** Google Gemini Flash API (`google-genai`), Hybrid Rule Engine
- **Frontend:** Single-Page Application (HTML5, Tailwind CSS, Lucide Icons, Canvas Particles)
- **Deployment:** 1-Click Cloud Ready (Render, Railway, Koyeb, Docker)

---

## 💻 Local Quickstart

```bash
# Clone the repository
git clone https://github.com/<your-username>/vertity-ai.git
cd vertity-ai

# Install dependencies
pip install -r requirements.txt

# Start the application
uvicorn main:app --host 0.0.0.0 --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.
