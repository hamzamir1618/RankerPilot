import os
import jinja2
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

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
    
    font_config = FontConfiguration()
    html = HTML(string=rendered_html)
    
    # Render PDF bytes
    pdf_bytes = html.write_pdf(font_config=font_config)
    return pdf_bytes
