"""
Gemini AI Content Auditor Module
Uses the official google-genai SDK to evaluate tone, unsupported claims, and brand compliance.
"""

import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List

# Define the Pydantic schema for structured output from Gemini
class FlaggedIssueSchema(BaseModel):
    category: str
    severity: str
    original_text_snippet: str
    explanation: str
    suggested_correction: str

class GeminiAuditResult(BaseModel):
    overall_compliance_score: int
    summary: str
    flagged_issues: List[FlaggedIssueSchema]

def audit_content_with_gemini(content_text: str, brand_guidelines_text: str) -> GeminiAuditResult:
    """
    Sends the draft content to Gemini Flash to analyze against brand rules.
    Requires GEMINI_API_KEY environment variable.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[Warning] GEMINI_API_KEY not found. Returning mock structured result.")
        return GeminiAuditResult(
            overall_compliance_score=75,
            summary="Content is mostly aligned but contains unsupported superlatives and slight tone mismatch.",
            flagged_issues=[
                FlaggedIssueSchema(
                    category="Legal & Claims",
                    severity="high",
                    original_text_snippet="guaranteed 100% bug-free",
                    explanation="Violates guideline on promotional guarantees without engineering verification.",
                    suggested_correction="designed for enterprise-grade reliability"
                )
            ]
        )

    client = genai.Client()

    prompt = f"""
    You are an enterprise Brand Governance and Compliance Auditor.
    Evaluate the following draft content strictly against the provided Brand Guidelines.
    
    BRAND GUIDELINES:
    {brand_guidelines_text}
    
    DRAFT CONTENT TO AUDIT:
    \"\"\"{content_text}\"\"\"
    
    Identify:
    1. Inconsistent tone (e.g. overly aggressive, sarcastic, or too casual).
    2. Unsupported or unverified promotional claims / superlatives (e.g. '#1', 'guaranteed').
    3. Forbidden terminology or missing preferred brand terms.
    4. Accessibility and clarity issues.
    
    For every issue, explain WHY it was flagged, and provide a suggested correction that PRESERVES THE CREATOR'S ORIGINAL PURPOSE.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeminiAuditResult,
            temperature=0.2,
        ),
    )

    return GeminiAuditResult.model_validate_json(response.text)

if __name__ == "__main__":
    sample_text = "Our tool is guaranteed 100% bug-free and the fastest in the world! All clients must buy now or regret it."
    guidelines = "Always use 'partners' instead of 'clients'. Never make absolute claims like 100% bug-free or fastest."
    print("Testing Gemini Auditor...")
    res = audit_content_with_gemini(sample_text, guidelines)
    print(res.model_dump_json(indent=2))
