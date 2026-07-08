from app.crawler.discovery import normalize_url, is_internal, get_registrable_domain

def test_normalize_url():
    # Test query param sorting
    assert normalize_url("http://example.com/page?b=2&a=1") == "http://example.com/page?a=1&b=2"
    
    # Test fragment stripping
    assert normalize_url("http://example.com/page#section") == "http://example.com/page"
    
    # Test relative path resolution
    assert normalize_url("/about", "http://example.com/") == "http://example.com/about"
    
    # Test lowercase domain
    assert normalize_url("HTTP://EXAMPLE.COM/Page") == "http://example.com/Page"
    
def test_registrable_domain():
    # Test tldextract boundaries
    assert get_registrable_domain("http://app.example.com") == "example.com"
    assert get_registrable_domain("https://example.co.uk") == "example.co.uk"
    assert get_registrable_domain("http://blog.example.co.uk/test") == "example.co.uk"
    assert get_registrable_domain("http://example.com") == "example.com"

def test_is_internal():
    base = "example.com"
    
    # Subdomain is internal
    assert is_internal("http://app.example.com/login", base) is True
    
    # Same domain is internal
    assert is_internal("https://example.com/about", base) is True
    
    # Different TLD is NOT internal
    assert is_internal("https://example.co.uk", base) is False
    
    # Different domain is NOT internal
    assert is_internal("https://google.com", base) is False
