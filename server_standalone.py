"""
Vertity AI - Zero-Dependency Backend Server
Inkloom AI Hackathon
Uses only Python standard library (http.server) to run without pip or venv issues.
Serves both JSON API endpoints and the frontend web app.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import urllib.parse

PORT = 8000
FRONTEND_FILE = os.path.join(os.path.dirname(__file__), "frontend_app.html")

# In-memory Brand Guidelines
BRAND_GUIDELINES = [
    {
        "id": "RULE-01",
        "category": "Tone & Terminology",
        "rule_name": "Customer Nomenclature",
        "description": "Always refer to clients as 'Growth Partners', never use 'clients' or 'users'.",
        "source_citation": "Brand Rulebook §1.2 (Customer Nomenclature)",
        "forbidden_terms": ["clients", "client", "users"],
        "approved_alternatives": ["Growth Partners", "growth partners", "partners"]
    },
    {
        "id": "RULE-02",
        "category": "Unsupported Claims",
        "rule_name": "Unsubstantiated Superlatives",
        "description": "Claims of '#1' or 'fastest in the world' require cited benchmark evidence.",
        "source_citation": "Brand Rulebook §4.1 (Legal Advertising & Superlatives)",
        "forbidden_terms": ["#1 fastest in the world", "#1", "fastest in the world"],
        "approved_alternatives": ["industry-leading", "high-performance"]
    },
    {
        "id": "RULE-03",
        "category": "Unsupported Claims",
        "rule_name": "Bug-Free Quality Guarantees",
        "description": "Absolute software guarantees like '100% bug-free' are legally impermissible.",
        "source_citation": "Brand Rulebook §4.2 (Technical SLA Claims)",
        "forbidden_terms": ["guaranteed 100% bug-free", "100% bug-free"],
        "approved_alternatives": ["engineered for 99.99% enterprise uptime"]
    },
    {
        "id": "RULE-05",
        "category": "Outdated Facts",
        "rule_name": "Approved 2025 Pricing",
        "description": "Legacy 2023 pricing of $49/mo is discontinued. The current Starter tier is $79/mo.",
        "source_citation": "Knowledge Base: Approved Pricing Q1 2025",
        "forbidden_terms": ["$49/mo", "$49 per month"],
        "approved_alternatives": ["$79/mo Starter Tier"]
    }
]

class VertityHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            if os.path.exists(FRONTEND_FILE):
                with open(FRONTEND_FILE, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"frontend_app.html not found.")
            return

        if path == "/api/health" or path == "/api/audit":
            res = {
                "status": "online",
                "service": "Vertity AI Governance Engine",
                "version": "1.0.0"
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        if path == "/api/guidelines":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(BRAND_GUIDELINES).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/audit":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                data = {}

            text = data.get("draft_text") or data.get("content_text") or ""
            text_lower = text.lower()

            flags = []
            flag_id = 1
            for rule in BRAND_GUIDELINES:
                for forbidden in rule["forbidden_terms"]:
                    if forbidden.lower() in text_lower:
                        flags.append({
                            "id": f"FLAG-{flag_id}",
                            "guideline_id": rule["id"],
                            "category": rule["category"],
                            "severity": "high" if "Claims" in rule["category"] or "Facts" in rule["category"] else "medium",
                            "original_text_snippet": forbidden,
                            "explanation": f"Violates {rule['rule_name']}: {rule['description']}",
                            "suggested_correction": rule["approved_alternatives"][0],
                            "source_citation": rule.get("source_citation", "Brand Rulebook §1.0"),
                            "check_type": "Deterministic Exact Match",
                            "confidence": "High (100% Rule Match)",
                            "issue_type": "violation"
                        })
                        flag_id += 1

            score = max(0, 100 - len(flags) * 15)
            status = "clean" if len(flags) == 0 else ("needs_review" if score > 60 else "flagged")

            response_data = {
                "submission_id": "SUB-LIVE",
                "overall_compliance_score": score,
                "status": status,
                "summary": f"Audit complete. Found {len(flags)} grounded issues against verified guidelines.",
                "flagged_issues": flags,
                "analyzed_at": "Just now"
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

def run():
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, VertityHandler)
    print("=" * 60)
    print(f"🛡️  Vertity AI Server RUNNING on http://127.0.0.1:{PORT}")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Vertity AI server...")

if __name__ == "__main__":
    run()
