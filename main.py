"""
Vertity AI - Backend Engine
Inkloom AI Hackathon
FastAPI backend for pre-publication brand governance, hybrid compliance auditing, and reviewer workflows.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from collections import Counter
import io
import zipfile
import os
import re
import json

# Import the AI/ML Engine
try:
    from ai_engine import analyze_content_text, analyze_brand_visuals, ContentAuditOutput, DEFAULT_APPROVED_PALETTE
    AI_ENGINE_LOADED = True
except ImportError:
    AI_ENGINE_LOADED = False
    DEFAULT_APPROVED_PALETTE = ["#6366F1", "#0F172A", "#06B6D4", "#FFFFFF", "#F8FAFC", "#1E293B", "#10B981"]

app = FastAPI(
    title="Vertity AI - Governance API",
    description="Intelligent Brand Governance API that reviews content against brand guidelines and approved facts.",
    version="1.0.0"
)

# Enable CORS so your Frontend team can connect seamlessly from React/Next.js/HTML
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure upload directory exists and mount static files
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
GUIDELINE_UPLOADS_DIR = os.path.join(UPLOADS_DIR, "guidelines")
VISUAL_UPLOADS_DIR = os.path.join(UPLOADS_DIR, "visuals")
os.makedirs(GUIDELINE_UPLOADS_DIR, exist_ok=True)
os.makedirs(VISUAL_UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# ---------------------------------------------------------
# DATA MODELS (Schemas for Requests and Responses)
# ---------------------------------------------------------

class BrandGuideline(BaseModel):
    id: str
    category: str  # "Outdated Facts", "Unsupported Claims", "Tone & Terminology", "Visuals", "Accessibility"
    rule_name: str
    description: str
    source_citation: Optional[str] = "Brand Rulebook Sec. 1.0"
    supporting_doc_name: Optional[str] = None
    supporting_doc_url: Optional[str] = None
    forbidden_terms: Optional[List[str]] = []
    approved_alternatives: Optional[List[str]] = []

class AuditRequest(BaseModel):
    title: Optional[str] = None
    document_title: Optional[str] = None
    content_type: Optional[str] = "blog"
    channel_source: Optional[str] = "External Agency"  # In-House, External Agency, Freelancer, Generative AI
    creator_name: Optional[str] = "Contributor"
    content_text: Optional[str] = None
    draft_text: Optional[str] = None

    def get_title(self) -> str:
        return self.document_title or self.title or "Untitled Document"

    def get_text(self) -> str:
        return self.draft_text or self.content_text or ""

    def get_channel(self) -> str:
        return self.channel_source or "In-House Draft"

class FlaggedIssue(BaseModel):
    id: Optional[str] = "FLAG-1"
    guideline_id: Optional[str] = None
    category: str  # "Outdated Facts", "Unsupported Claims", "Tone & Terminology", "Visuals", "Accessibility"
    severity: str  # "high", "medium", "low"
    original_text_snippet: str
    explanation: str
    suggested_correction: str
    source_citation: Optional[str] = "Brand Rulebook Sec. 1.0"
    supporting_doc_name: Optional[str] = None
    supporting_doc_url: Optional[str] = None
    check_type: Optional[str] = "Deterministic Rule"  # "Deterministic Rule" or "Semantic LLM"
    confidence: Optional[str] = "High (100% Deterministic)"
    issue_type: Optional[str] = "violation"  # "violation" (grounded source) or "suggestion" (heuristic)

class AuditResponse(BaseModel):
    submission_id: str
    overall_compliance_score: int  # 0 to 100
    status: str  # "clean", "needs_review", "flagged"
    summary: str
    flagged_issues: List[FlaggedIssue]
    analyzed_at: str

class InlineAuditRequest(BaseModel):
    text: str
    page_url: Optional[str] = ""
    page_title: Optional[str] = ""
    platform: Optional[str] = "Web Editor"
    include_ai: Optional[bool] = False

class InlineFlaggedSpan(BaseModel):
    id: str
    guideline_id: Optional[str] = None
    category: str
    severity: str
    original_text_snippet: str
    start_index: int
    end_index: int
    explanation: str
    suggested_correction: str
    source_citation: str
    check_type: str

class InlineAuditResponse(BaseModel):
    overall_compliance_score: int
    status: str
    summary: str
    platform: str
    flagged_issues: List[InlineFlaggedSpan]
    analyzed_at: str
    persisted: bool = False

# ---------------------------------------------------------
# IN-MEMORY KNOWLEDGE BASE (Guidelines & Approved Facts)
# ---------------------------------------------------------

BRAND_GUIDELINES = [
    {
        "id": "RULE-01",
        "category": "Tone & Terminology",
        "rule_name": "Customer Nomenclature Standards",
        "description": "Always refer to clients as 'Growth Partners', never use 'clients' or 'users'.",
        "source_citation": "Brand Rulebook Sec. 1.2 (Customer Nomenclature)",
        "supporting_doc_name": "Customer_Nomenclature_SOP_2025.pdf",
        "forbidden_terms": ["clients", "client", "users"],
        "approved_alternatives": ["Growth Partners", "growth partners", "partners"]
    },
    {
        "id": "RULE-02",
        "category": "Unsupported Claims",
        "rule_name": "Unsubstantiated Promotional Superlatives",
        "description": "Claims of '#1' or 'fastest in the world' are prohibited without citing verified third-party benchmark evidence.",
        "source_citation": "Brand Rulebook Sec. 4.1 (Legal Advertising & Superlatives)",
        "supporting_doc_name": "Legal_Claims_Verification_Manual.pdf",
        "forbidden_terms": ["#1 fastest in the world", "#1", "fastest in the world"],
        "approved_alternatives": ["industry-leading", "high-performance", "top-tier"]
    },
    {
        "id": "RULE-03",
        "category": "Unsupported Claims",
        "rule_name": "Absolute Software Quality Guarantees",
        "description": "Absolute guarantees like '100% bug-free' violate legal advertising compliance; use SLA uptime metrics.",
        "source_citation": "Brand Rulebook Sec. 4.2 (Technical SLA & Quality Claims)",
        "supporting_doc_name": "SLA_Engineering_Reliability_Policy.pdf",
        "forbidden_terms": ["guaranteed 100% bug-free", "100% bug-free", "zero bugs"],
        "approved_alternatives": ["engineered for enterprise-grade 99.99% reliability", "thoroughly verified"]
    },
    {
        "id": "RULE-04",
        "category": "Unsupported Claims",
        "rule_name": "Unverified Financial ROI Claims",
        "description": "Promising 'undisputed 10x ROI' creates regulatory risk without customer case study citations.",
        "source_citation": "Brand Rulebook Sec. 4.3 (Financial & Metrics Substantiation)",
        "forbidden_terms": ["undisputed 10x ROI", "10x ROI without question", "10x ROI"],
        "approved_alternatives": ["proven multi-fold ROI across enterprise deployments", "measurable ROI"]
    },
    {
        "id": "RULE-05",
        "category": "Outdated Facts",
        "rule_name": "Approved 2025 Pricing & Packaging",
        "description": "Legacy 2023 pricing of '$49/mo' has been discontinued. The approved Starter package is '$79/mo'.",
        "source_citation": "Knowledge Base: Approved Pricing & Fact Sheet Q1 2025",
        "supporting_doc_name": "Q1_2025_Enterprise_Pricing_Fact_Sheet.pdf",
        "forbidden_terms": ["$49/mo", "$49 per month", "$49/month"],
        "approved_alternatives": ["$79/mo Starter Tier", "Enterprise Tier"]
    },
    {
        "id": "RULE-06",
        "category": "Tone & Terminology",
        "rule_name": "Empathetic, Professional & Non-Aggressive Voice",
        "description": "Avoid aggressive pressure tactics ('buy now or regret it') or dismissive slang ('stupid simple', 'obviously').",
        "source_citation": "Brand Rulebook Sec. 1.3 (Voice, Empathy & Professionalism)",
        "forbidden_terms": ["buy now or regret it", "obviously", "stupid simple"],
        "approved_alternatives": ["explore the platform today", "demonstrably", "intuitively designed"]
    },
    {
        "id": "RULE-07",
        "category": "Visuals",
        "rule_name": "Approved Brand Asset & Color Standards",
        "description": "Only use Primary Indigo (#6366F1), Slate Dark (#0F172A), and Cyan Accent (#06B6D4). Unapproved neon/red colors violate brand guidelines.",
        "source_citation": "Brand Identity Manual Sec. 3.0 (Color System & Approved Palette)",
        "supporting_doc_name": "Brand_Identity_Color_Palette_v2.pdf",
        "forbidden_terms": ["legacy blue logo", "deprecated icon set"],
        "approved_alternatives": ["Vertity Modern Mark v2.4", "approved enterprise icon set"]
    },
    {
        "id": "RULE-08",
        "category": "Accessibility",
        "rule_name": "Accessibility & Inclusive Design Standards",
        "description": "All published media must meet WCAG 2.1 AA standards (minimum 4.5:1 text-to-background contrast ratio and descriptive alt text).",
        "source_citation": "WCAG 2.1 AA Digital Accessibility Standard Sec. 1.4.3",
        "supporting_doc_name": "WCAG_2.1_AA_Accessibility_Standard.pdf",
        "forbidden_terms": ["low contrast text", "missing alt text"],
        "approved_alternatives": ["high-contrast AA compliant formatting", "descriptive alt text"]
    }
]

# Simple in-memory storage for hackathon submissions with pre-loaded demo records
SUBMISSIONS_DB = {
    "SUB-0001": {
        "request": {
            "title": "Cloud Infrastructure Migration Announcement",
            "content_type": "social_media",
            "channel_source": "External Agency Draft",
            "creator_name": "External Agency",
            "content_text": "We are proud to serve our clients with the fastest in the world transaction speeds at just $49/mo."
        },
        "response": {
            "submission_id": "SUB-0001",
            "overall_compliance_score": 62,
            "status": "needs_review",
            "summary": "Flagged 3 grounded issues: outdated pricing ($49/mo), unverified superlative claim, and client terminology drift.",
            "flagged_issues": [
                {
                    "id": "FLAG-1",
                    "guideline_id": "RULE-05",
                    "category": "Outdated Facts",
                    "severity": "high",
                    "original_text_snippet": "$49/mo",
                    "explanation": "Violates Approved 2025 Pricing: Legacy 2023 pricing has been discontinued. The approved Starter tier is $79/mo.",
                    "suggested_correction": "$79/mo Starter Tier",
                    "source_citation": "Knowledge Base: Approved Pricing & Fact Sheet Q1 2025",
                    "check_type": "Deterministic Exact Match",
                    "confidence": "High (100% Rule Match)",
                    "issue_type": "violation"
                },
                {
                    "id": "FLAG-2",
                    "guideline_id": "RULE-02",
                    "category": "Unsupported Claims",
                    "severity": "high",
                    "original_text_snippet": "fastest in the world",
                    "explanation": "Violates Unsubstantiated Promotional Superlatives: Speed claims require cited benchmark reports.",
                    "suggested_correction": "industry-leading",
                    "source_citation": "Brand Rulebook §4.1 (Legal Advertising & Superlatives)",
                    "check_type": "Deterministic Exact Match",
                    "confidence": "High (100% Rule Match)",
                    "issue_type": "violation"
                },
                {
                    "id": "FLAG-3",
                    "guideline_id": "RULE-01",
                    "category": "Tone & Terminology",
                    "severity": "medium",
                    "original_text_snippet": "clients",
                    "explanation": "Violates Customer Nomenclature Standards: Always refer to clients as 'Growth Partners'.",
                    "suggested_correction": "Growth Partners",
                    "source_citation": "Brand Rulebook §1.2 (Customer Nomenclature)",
                    "check_type": "Deterministic Exact Match",
                    "confidence": "High (100% Rule Match)",
                    "issue_type": "violation"
                }
            ],
            "analyzed_at": "2026-11-04T09:15:00Z"
        },
        "workflow_state": "AI Audited"
    },
    "SUB-0002": {
        "request": {
            "title": "Partner Ecosystem Quarterly Newsletter",
            "content_type": "blog",
            "channel_source": "In-House Marketing",
            "creator_name": "In-House Team",
            "content_text": "We are delighted to celebrate our growth partners with high-performance infrastructure engineered for 99.99% availability."
        },
        "response": {
            "submission_id": "SUB-0002",
            "overall_compliance_score": 96,
            "status": "clean",
            "summary": "Content aligns strongly with brand tone, verified fact sheet, and preferred terminology.",
            "flagged_issues": [],
            "analyzed_at": "2026-11-04T08:30:00Z"
        },
        "workflow_state": "Approved",
        "approved_by": "Brand Governance Director",
        "approved_at": "2026-11-04T08:45:00Z"
    }
}

# ---------------------------------------------------------
# COMPLIANCE AUDIT ENGINE
# ---------------------------------------------------------

def evaluate_content_rules(text: str) -> List[FlaggedIssue]:
    """
    Evaluates text against deterministic brand rules with grounded source citations.
    Hybrid Principle: Exact rules (terms, pricing, superlatives) are checked deterministically;
    Nuanced tone & claim judgements use Gemini LLM.
    """
    flags = []
    text_lower = text.lower()

    for rule in BRAND_GUIDELINES:
        for forbidden in rule.get("forbidden_terms", []):
            if forbidden.lower() in text_lower:
                severity = "high" if rule["category"] in ["Unsupported Claims", "Outdated Facts"] else "medium"
                flags.append(FlaggedIssue(
                    guideline_id=rule["id"],
                    category=rule["category"],
                    severity=severity,
                    original_text_snippet=forbidden,
                    explanation=f"Violates {rule['rule_name']}: {rule['description']}",
                    suggested_correction=rule["approved_alternatives"][0] if rule.get("approved_alternatives") else "Revise or remove",
                    source_citation=rule.get("source_citation", "Brand Rulebook Sec. 1.0"),
                    supporting_doc_name=rule.get("supporting_doc_name"),
                    supporting_doc_url=rule.get("supporting_doc_url"),
                    check_type="Deterministic Exact Match",
                    confidence="High (100% Rule Match)",
                    issue_type="violation"
                ))
    
    return flags

def _evaluate_inline_spans(text: str) -> List[InlineFlaggedSpan]:
    """
    Longest-match non-overlapping deterministic span detector for the Chrome Extension
    and CMS live inline copilot. Prevents duplicate overlaps like 'clients' vs 'client'
    or 'guaranteed 100% bug-free' vs '100% bug-free'.
    """
    if not text:
        return []

    term_entries = []
    for rule in BRAND_GUIDELINES:
        for forbidden in rule.get("forbidden_terms", []):
            term = forbidden.strip()
            if term:
                term_entries.append((term, rule))

    # Longest phrases first so specific multi-word violations win over shorter substrings
    term_entries.sort(key=lambda item: len(item[0]), reverse=True)

    occupied_ranges = []
    raw_spans: List[InlineFlaggedSpan] = []

    for term, rule in term_entries:
        prefix = r"(?<!\w)" if term[0].isalnum() else ""
        suffix = r"(?!\w)" if term[-1].isalnum() else ""
        pattern = re.compile(f"{prefix}{re.escape(term)}{suffix}", re.IGNORECASE)

        for match in pattern.finditer(text):
            s, e = match.start(), match.end()
            if any(not (e <= os_ or s >= oe) for os_, oe in occupied_ranges):
                continue
            occupied_ranges.append((s, e))
            severity = "high" if rule["category"] in ["Unsupported Claims", "Outdated Facts"] else "medium"
            raw_spans.append(InlineFlaggedSpan(
                id="INLINE-PENDING",
                guideline_id=rule["id"],
                category=rule["category"],
                severity=severity,
                original_text_snippet=text[s:e],
                start_index=s,
                end_index=e,
                explanation=f"Violates {rule['rule_name']}: {rule['description']}",
                suggested_correction=rule["approved_alternatives"][0] if rule.get("approved_alternatives") else "Revise or remove",
                source_citation=rule.get("source_citation", "Brand Rulebook Sec. 1.0"),
                check_type="Deterministic Inline Span"
            ))

    raw_spans.sort(key=lambda sp: sp.start_index)
    for idx, sp in enumerate(raw_spans, start=1):
        sp.id = f"INLINE-{idx}"
    return raw_spans

# ---------------------------------------------------------
# API ENDPOINTS
# ---------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def serve_frontend_app():
    """Serves the Vertity AI web application directly at the root URL."""
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend_app.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return HTMLResponse("<h2>Vertity AI Backend is Running. frontend_app.html not found.</h2>")

@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": "Vertity AI Governance API",
        "version": "1.0.0",
        "docs_url": "http://127.0.0.1:8000/docs"
    }

@app.get("/api/guidelines", response_model=List[BrandGuideline])
def get_guidelines():
    """Returns the company's approved brand guidelines and rules."""
    return BRAND_GUIDELINES

@app.get("/api/audit")
def audit_status_check():
    """Health check for Frontend UI header status indicator."""
    return {"status": "online", "service": "Vertity AI Audit Service"}

@app.post("/api/audit", response_model=AuditResponse)
def audit_content(payload: AuditRequest):
    """
    Main Endpoint: Receives content draft and returns compliance score,
    flagged issues, explanations, and suggested corrections.
    Combines fast deterministic rules with Gemini AI semantic auditing.
    """
    text_to_audit = payload.get_text()
    title_to_audit = payload.get_title()

    all_flags = []
    flag_counter = 1

    # 1. Deterministic Rule Matching (Banned words, strict terminology)
    det_flags = evaluate_content_rules(text_to_audit)
    for f in det_flags:
        f.id = f"FLAG-{flag_counter}"
        flag_counter += 1
        all_flags.append(f)

    # 2. Semantic AI Auditing via Gemini (if ai_engine is loaded)
    ai_summary = f"Content audited for draft '{title_to_audit}' against brand guidelines."
    ai_score = 100 - (len(all_flags) * 15)

    if AI_ENGINE_LOADED and text_to_audit:
        try:
            guidelines_text = "\n".join([f"- {r['category']}: {r['description']}" for r in BRAND_GUIDELINES])
            ai_output = analyze_content_text(text_to_audit, guidelines_text)
            ai_summary = ai_output.summary
            ai_score = ai_output.overall_compliance_score

            # Append any unique issues flagged by the AI
            existing_snippets = {f.original_text_snippet.lower() for f in all_flags}
            for issue in ai_output.flagged_issues:
                if issue.original_text_snippet.lower() not in existing_snippets:
                    all_flags.append(FlaggedIssue(
                        id=f"FLAG-{flag_counter}",
                        category=issue.category,
                        severity=issue.severity,
                        original_text_snippet=issue.original_text_snippet,
                        explanation=issue.explanation,
                        suggested_correction=issue.suggested_correction,
                        source_citation=getattr(issue, 'source_citation', 'Brand Knowledge Base §1.0'),
                        check_type=getattr(issue, 'check_type', 'Semantic LLM'),
                        confidence=getattr(issue, 'confidence', 'High (92% Grounded)'),
                        issue_type=getattr(issue, 'issue_type', 'violation')
                    ))
                    flag_counter += 1
        except Exception as e:
            print(f"[Warning] AI Engine call failed gracefully: {e}")

    # Determine status & final compliance score
    final_score = max(0, min(100, ai_score if AI_ENGINE_LOADED else (100 - len(all_flags) * 15)))
    status = "clean" if len(all_flags) == 0 else ("needs_review" if final_score > 60 else "flagged")
    submission_id = f"SUB-{len(SUBMISSIONS_DB) + 1:04d}"

    result = AuditResponse(
        submission_id=submission_id,
        overall_compliance_score=final_score,
        status=status,
        summary=ai_summary,
        flagged_issues=all_flags,
        analyzed_at=datetime.utcnow().isoformat()
    )

    # Save to in-memory history for review workflow
    SUBMISSIONS_DB[submission_id] = {
        "request": payload.dict(),
        "response": result.dict(),
        "workflow_state": "AI Audited"
    }

    return result

@app.post("/api/audit-visual")
async def audit_visual_asset(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    channel_source: Optional[str] = Form("Creative Visual Upload"),
    creator_name: Optional[str] = Form("Design Team")
):
    """
    Round 3 Improvement 1: Multimodal Visual Banner & WCAG 2.1 AA Accessibility Auditor.
    Extracts actual hex swatches via Pillow quantization, computes WCAG 2.1 luminance contrast ratios,
    and performs Gemini Vision inspection for OCR copy drift, logo detection, alt-text, and region heatmaps.
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image file is empty")

    # Sanitize filename and save visual asset
    safe_name = os.path.basename(file.filename or "banner_upload.png").replace(" ", "_")
    saved_path = os.path.join(VISUAL_UPLOADS_DIR, safe_name)
    try:
        with open(saved_path, "wb") as f:
            f.write(image_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store visual asset: {e}")

    # Dynamically extract approved hex palette tokens from Rulebook Visuals rules
    approved_hexes = []
    for rule in BRAND_GUIDELINES:
        if rule.get("category") in ("Visuals", "Accessibility"):
            found_hexes = re.findall(r"#[0-9A-Fa-f]{6}", rule.get("description", ""))
            approved_hexes.extend([h.upper() for h in found_hexes])
    # Always merge baseline neutrals & brand tokens so neutral text/surfaces aren't penalized
    merged_palette = list(dict.fromkeys(approved_hexes + DEFAULT_APPROVED_PALETTE))

    guidelines_text = "\n".join([f"- [{r['id']}] {r['category']}: {r['description']}" for r in BRAND_GUIDELINES])

    if not AI_ENGINE_LOADED:
        raise HTTPException(status_code=503, detail="Visual AI Engine not loaded")

    try:
        visual_output = analyze_brand_visuals(image_bytes, merged_palette, guidelines_text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not analyze image file: {e}")

    # Convert visual & accessibility region findings + any OCR text drift into standard FlaggedIssue objects
    all_flags: List[FlaggedIssue] = []
    flag_counter = 1

    for region in visual_output.flagged_regions:
        rule_id = "RULE-07" if region.category == "Visuals" else ("RULE-08" if region.category == "Accessibility" else "RULE-02")
        all_flags.append(FlaggedIssue(
            id=f"FLAG-{flag_counter}",
            guideline_id=rule_id,
            category=region.category,
            severity=region.severity,
            original_text_snippet=region.label,
            explanation=region.explanation,
            suggested_correction=region.suggested_fix,
            source_citation=region.source_citation,
            check_type="Pillow Color/WCAG Math + Vision",
            confidence="High (Pixel + WCAG Verified)",
            issue_type="violation"
        ))
        flag_counter += 1

    # Also run deterministic text rules against any OCR text extracted from the banner
    if visual_output.extracted_text_ocr and "Deterministic pixel" not in visual_output.extracted_text_ocr:
        ocr_flags = evaluate_content_rules(visual_output.extracted_text_ocr)
        for f in ocr_flags:
            f.id = f"FLAG-{flag_counter}"
            f.check_type = "Vision OCR + Deterministic Rule"
            all_flags.append(f)
            flag_counter += 1

    final_score = visual_output.overall_compliance_score
    if len(all_flags) == 0 and final_score >= 85:
        status = "clean"
    elif final_score >= 60:
        status = "needs_review"
    else:
        status = "flagged"

    submission_id = f"SUB-{len(SUBMISSIONS_DB) + 1:04d}"
    doc_title = title or f"Visual Asset: {safe_name}"
    analyzed_at = datetime.utcnow().isoformat()

    response_payload = {
        "submission_id": submission_id,
        "overall_compliance_score": final_score,
        "status": status,
        "summary": visual_output.visual_feedback,
        "flagged_issues": [f.dict() for f in all_flags],
        "analyzed_at": analyzed_at,
        "visual_audit": {
            "filename": safe_name,
            "image_url": f"/uploads/visuals/{safe_name}",
            "image_dimensions": visual_output.image_dimensions,
            "analysis_mode": visual_output.analysis_mode,
            "palette_compliance_score": visual_output.palette_compliance_score,
            "dominant_colors_hex": visual_output.dominant_colors_hex,
            "swatches": [s.dict() for s in visual_output.swatches],
            "contrast_audit": visual_output.contrast_audit.dict(),
            "brand_logo_detected": visual_output.brand_logo_detected,
            "extracted_text_ocr": visual_output.extracted_text_ocr,
            "generated_alt_text": visual_output.generated_alt_text,
            "flagged_regions": [r.dict() for r in visual_output.flagged_regions],
        }
    }

    SUBMISSIONS_DB[submission_id] = {
        "request": {
            "title": doc_title,
            "content_type": "visual_banner",
            "channel_source": channel_source,
            "creator_name": creator_name,
            "content_text": f"[Visual Asset {safe_name}] {visual_output.extracted_text_ocr}"
        },
        "response": response_payload,
        "workflow_state": "AI Audited"
    }

    return response_payload

@app.post("/api/audit-inline", response_model=InlineAuditResponse)
def audit_inline_draft(payload: InlineAuditRequest):
    """
    Round 3 Improvement 2: Ultra-fast non-persisting live linting endpoint for the
    Vertity AI Chrome/Edge Browser Extension (Google Docs, LinkedIn, WordPress, CMS).
    Does NOT insert keystroke drafts into SUBMISSIONS_DB.
    """
    text = payload.text or ""
    spans = _evaluate_inline_spans(text)

    penalty = sum(18 if sp.severity == "high" else 10 for sp in spans)
    score = max(0, 100 - penalty)
    ai_summary = (
        f"Flagged {len(spans)} grounded issue(s) inline in {payload.platform}."
        if spans else
        f"Clean draft in {payload.platform}: zero Brand Rulebook drift detected."
    )

    if payload.include_ai and AI_ENGINE_LOADED and len(text.strip()) >= 25:
        try:
            guidelines_text = "\n".join([f"- {r['category']}: {r['description']}" for r in BRAND_GUIDELINES])
            ai_output = analyze_content_text(text, guidelines_text)
            score = max(0, min(100, min(score, ai_output.overall_compliance_score)))
            if ai_output.summary:
                ai_summary = ai_output.summary
            existing_lower = {sp.original_text_snippet.lower() for sp in spans}
            next_idx = len(spans) + 1
            for issue in ai_output.flagged_issues:
                snip = (issue.original_text_snippet or "").strip()
                if not snip or snip.lower() in existing_lower:
                    continue
                pos = text.lower().find(snip.lower())
                if pos == -1:
                    continue
                end_pos = pos + len(snip)
                if any(not (end_pos <= sp.start_index or pos >= sp.end_index) for sp in spans):
                    continue
                spans.append(InlineFlaggedSpan(
                    id=f"INLINE-{next_idx}",
                    guideline_id=None,
                    category=issue.category,
                    severity=issue.severity,
                    original_text_snippet=text[pos:end_pos],
                    start_index=pos,
                    end_index=end_pos,
                    explanation=issue.explanation,
                    suggested_correction=issue.suggested_correction,
                    source_citation=getattr(issue, "source_citation", "Brand Rulebook §1.0"),
                    check_type=getattr(issue, "check_type", "Semantic LLM Inline")
                ))
                existing_lower.add(snip.lower())
                next_idx += 1
        except Exception as e:
            print(f"[Inline AI Warning] {e}")

    status = "clean" if len(spans) == 0 else ("needs_review" if score > 60 else "flagged")
    return InlineAuditResponse(
        overall_compliance_score=score,
        status=status,
        summary=ai_summary,
        platform=payload.platform or "Web Editor",
        flagged_issues=spans,
        analyzed_at=datetime.utcnow().isoformat(),
        persisted=False
    )

@app.get("/api/extension/download")
def download_chrome_extension():
    """
    Round 3 Improvement 2: Packages the Manifest V3 Vertity AI Browser Extension
    (`chrome_extension/`) into an instant downloadable ZIP bundle for Chrome/Edge Developer Mode.
    """
    ext_dir = os.path.join(os.path.dirname(__file__), "chrome_extension")
    if not os.path.isdir(ext_dir):
        raise HTTPException(status_code=404, detail="chrome_extension package directory not found")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root_dir, _, files in os.walk(ext_dir):
            for fname in sorted(files):
                abs_path = os.path.join(root_dir, fname)
                rel_path = os.path.relpath(abs_path, ext_dir).replace("\\", "/")
                zf.write(abs_path, arcname=rel_path)

    zip_buffer.seek(0)
    headers = {
        "Content-Disposition": 'attachment; filename="Vertity-AI-Chrome-Extension.zip"',
        "Cache-Control": "no-cache"
    }
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)

@app.get("/api/submissions")
def list_submissions():
    """Lists all submitted documents for the Review & Approval dashboard."""
    return list(SUBMISSIONS_DB.values())

@app.post("/api/submissions/{sub_id}/approve")
def approve_submission(sub_id: str, reviewer_name: str = "Brand Manager"):
    """Approves a document for final publication."""
    if sub_id not in SUBMISSIONS_DB:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    SUBMISSIONS_DB[sub_id]["workflow_state"] = "Approved"
    SUBMISSIONS_DB[sub_id]["approved_by"] = reviewer_name
    SUBMISSIONS_DB[sub_id]["approved_at"] = datetime.utcnow().isoformat()
    
    return {"message": f"Submission {sub_id} successfully approved by {reviewer_name}!"}

@app.post("/api/submissions/{sub_id}/reject")
def reject_submission(sub_id: str, reviewer_name: str = "Brand Manager", notes: str = "Please revise flagged areas."):
    """Requests revisions from the creator with reviewer notes."""
    if sub_id not in SUBMISSIONS_DB:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    SUBMISSIONS_DB[sub_id]["workflow_state"] = "Revision Requested"
    SUBMISSIONS_DB[sub_id]["reviewer_notes"] = notes
    SUBMISSIONS_DB[sub_id]["reviewed_by"] = reviewer_name
    SUBMISSIONS_DB[sub_id]["reviewed_at"] = datetime.utcnow().isoformat()
    
    return {
        "submission_id": sub_id,
        "workflow_state": "Revision Requested",
        "notes": notes,
        "message": f"Revision requested for {sub_id}."
    }

@app.post("/api/audit-file", response_model=AuditResponse)
async def audit_file(
    file: UploadFile = File(...),
    content_type: str = Form("document"),
    creator_name: str = Form("Creator")
):
    """
    Multi-Format Document Upload: Accepts .txt, .md, .csv, or text files,
    extracts the text, and runs the brand governance audit pipeline.
    """
    try:
        content_bytes = await file.read()
        text = content_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")
    
    if not text.strip():
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    
    payload = AuditRequest(
        title=file.filename or "Uploaded Document",
        content_type=content_type,
        content_text=text,
        creator_name=creator_name
    )
    return audit_content(payload)

@app.post("/api/guidelines", response_model=BrandGuideline)
def add_guideline(rule: BrandGuideline):
    """Admin Only: Allows Brand Admins to add a new guideline rule dynamically."""
    for r in BRAND_GUIDELINES:
        if r["id"] == rule.id:
            raise HTTPException(status_code=400, detail="Guideline ID already exists")
    
    BRAND_GUIDELINES.append(rule.dict())
    return rule

@app.put("/api/guidelines/{rule_id}", response_model=BrandGuideline)
def update_guideline(rule_id: str, updated_rule: BrandGuideline):
    """Admin Only: Allows Brand Admins to update an existing guideline rule."""
    for i, r in enumerate(BRAND_GUIDELINES):
        if r["id"] == rule_id:
            BRAND_GUIDELINES[i] = updated_rule.dict()
            return updated_rule
    raise HTTPException(status_code=404, detail=f"Guideline {rule_id} not found")

@app.delete("/api/guidelines/{rule_id}")
def delete_guideline(rule_id: str):
    """Admin Only: Allows Brand Admins to delete a guideline rule."""
    global BRAND_GUIDELINES
    initial_len = len(BRAND_GUIDELINES)
    BRAND_GUIDELINES = [r for r in BRAND_GUIDELINES if r["id"] != rule_id]
    if len(BRAND_GUIDELINES) == initial_len:
        raise HTTPException(status_code=404, detail=f"Guideline {rule_id} not found")
    return {"message": f"Guideline {rule_id} successfully deleted", "id": rule_id}

@app.post("/api/guidelines/upload-doc")
async def upload_guideline_document(file: UploadFile = File(...)):
    """Admin Only: Uploads a supporting brand book excerpt or policy fact sheet document."""
    file_path = os.path.join(GUIDELINE_UPLOADS_DIR, file.filename)
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        return {
            "status": "success",
            "filename": file.filename,
            "file_size": len(content),
            "file_url": f"/uploads/guidelines/{file.filename}",
            "message": f"Document '{file.filename}' attached successfully!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {e}")

@app.get("/api/analytics")
def get_governance_analytics():
    """
    Governance Insights Engine: Aggregates repeated mistakes across all drafts,
    identifying unclear brand guidelines and common compliance pitfalls.
    """
    total_submissions = len(SUBMISSIONS_DB)
    if total_submissions == 0:
        return {
            "total_audited_documents": 0,
            "average_compliance_score": 100,
            "status_breakdown": {"clean": 0, "needs_review": 0, "flagged": 0},
            "category_violation_counts": {},
            "top_violation_terms": [],
            "executive_governance_insights": [
                "No submissions recorded yet. The system is ready to audit content."
            ]
        }
    
    all_scores = []
    status_counts = Counter()
    category_counts = Counter()
    term_counts = Counter()

    for item in SUBMISSIONS_DB.values():
        resp = item.get("response", {})
        all_scores.append(resp.get("overall_compliance_score", 100))
        status_counts[resp.get("status", "clean")] += 1
        for issue in resp.get("flagged_issues", []):
            cat = issue.get("category", "General")
            category_counts[cat] += 1
            snippet = issue.get("original_text_snippet", "")
            if snippet:
                term_counts[snippet.lower()] += 1

    avg_score = round(sum(all_scores) / len(all_scores), 1)

    # Generate explainable governance insights
    insights = []
    if category_counts:
        top_cat, top_cat_count = category_counts.most_common(1)[0]
        insights.append(
            f"'{top_cat}' is the most frequent violation category ({top_cat_count} occurrences). Consider clarifying related policy documentation."
        )
    if term_counts:
        top_term, top_term_count = term_counts.most_common(1)[0]
        insights.append(
            f"The term '{top_term}' was repeatedly flagged ({top_term_count} times). Ensure all writers are updated with approved synonyms."
        )
    if avg_score < 70:
        insights.append("Company-wide compliance score is below target (70%). Pre-publication AI linting should be mandated across all teams.")
    else:
        insights.append("Overall brand compliance is healthy. High adoption of verified brand standards observed.")

    return {
        "total_audited_documents": total_submissions,
        "average_compliance_score": avg_score,
        "status_breakdown": dict(status_counts),
        "category_violation_counts": dict(category_counts),
        "top_violation_terms": [
            {"term": term, "count": count} for term, count in term_counts.most_common(5)
        ],
        "executive_governance_insights": insights
    }

if __name__ == "__main__":
    import uvicorn
    # Support dynamic PORT environment variable provided by cloud hosts (Render, Railway, Heroku)
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
