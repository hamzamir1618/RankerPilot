import pytest
from app.reports.generator import generate_pdf_report, env

def test_pdf_generation_and_injection():
    # Test HTML injection escaping
    context = {
        "project_name": "Test Project",
        "domain": "test.com",
        "score": 85,
        "date": "2023-01-01",
        "action_plan": [
            {
                "title": "<script>alert(1)</script>", # HTML injection
                "severity": "critical",
                "effort": "immediate",
                "category": "technical",
                "fix": "Remove the script <style>body{display:none}</style>" # CSS injection
            }
        ],
        "findings_by_category": {
            "technical": [
                {
                    "title": "Normal finding",
                    "severity": "low",
                    "evidence": {"info": "all good"},
                    "fix": "none"
                }
            ]
        }
    }
    
    # First, test the raw HTML template to verify Jinja2 escaping
    template = env.get_template("report.html")
    rendered_html = template.render(**context)
    
    # The payload should be escaped, so we shouldn't see raw tags
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered_html
    assert "<script>alert(1)</script>" not in rendered_html
    assert "&lt;style&gt;body{display:none}&lt;/style&gt;" in rendered_html
    
    # Second, generate the PDF to verify weasyprint doesn't crash and generates a valid PDF
    pdf_bytes = generate_pdf_report(context)
    
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-")
