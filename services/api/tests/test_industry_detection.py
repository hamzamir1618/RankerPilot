from app.services.industry_detection import detect_industry
from app.agents.base import AuditContext
from app.schemas.schemas import PageResponse
import uuid
import datetime

def create_mock_context(texts: list[str]) -> AuditContext:
    pages = []
    for t in texts:
        p = PageResponse(
            id=uuid.uuid4(),
            audit_id=uuid.uuid4(),
            url="http://example.com",
            status_code=200,
            rendered=True,
            title=t,
            meta_description="",
            h1=[],
            word_count=len(t.split()),
            fetched_at=datetime.datetime.now()
        )
        pages.append(p)
        
    return AuditContext(
        audit_id=str(uuid.uuid4()),
        pages=pages,
        site_graph={},
        robots_txt=None,
        sitemap_urls=[],
        industry="saas"
    )

def test_industry_detection_saas():
    ctx = create_mock_context(["We build the best software platform for you. See our pricing."])
    result = detect_industry(ctx)
    assert result["industry"] == "saas"

def test_industry_detection_ecommerce():
    ctx = create_mock_context(["Add to cart and checkout your favorite product."])
    result = detect_industry(ctx)
    assert result["industry"] == "ecommerce"

def test_industry_detection_local_service():
    ctx = create_mock_context(["Call our phone number to book an appointment for roofing."])
    result = detect_industry(ctx)
    assert result["industry"] == "local_service"

def test_industry_detection_publisher():
    ctx = create_mock_context(["Read our latest article on the blog."])
    result = detect_industry(ctx)
    assert result["industry"] == "publisher"

def test_industry_detection_agency():
    ctx = create_mock_context(["View our portfolio and case study for marketing services."])
    result = detect_industry(ctx)
    assert result["industry"] == "agency"

def test_industry_detection_ambiguous_fallback():
    # Tie between SaaS and Ecommerce (both have 1 signal)
    ctx = create_mock_context(["software product"])
    
    # We didn't provide an LLM client, so it falls back to the default fallback (saas)
    result = detect_industry(ctx)
    assert result["industry"] == "saas"
    assert "LLM fallback" in result["reasoning"]
