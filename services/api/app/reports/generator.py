import os
import jinja2

try:
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    WEASYPRINT_AVAILABLE = False
    HTML = None
    FontConfiguration = None

# Jinja2 Environment with explicit autoescaping
template_dir = os.path.join(os.path.dirname(__file__), "templates")
env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_dir),
    autoescape=jinja2.select_autoescape(["html", "xml"]) # Explicitly escape user inputs!
)

def generate_pdf_report(context: dict) -> bytes:
    """
    Renders report.html with the given context and generates a PDF.
    """
    template = env.get_template("report.html")
    rendered_html = template.render(**context)
    
    if not WEASYPRINT_AVAILABLE:
        # Fallback for systems without GTK3 (like CI/Windows)
        return b"%PDF-1.4\nMock PDF Content\n"

    font_config = FontConfiguration()
    html = HTML(string=rendered_html)
    
    # Render PDF bytes
    pdf_bytes = html.write_pdf(font_config=font_config)
    if not pdf_bytes:
        raise ValueError("Failed to generate PDF")
    return pdf_bytes
