import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # 1. Login
            print("Navigating to login page...")
            await page.goto("http://localhost:3000/login")
            await page.fill("input[type='email']", "demo@rankerpilot.com")
            await page.fill("input[type='password']", "demo_password")
            
            print("Clicking Sign In...")
            await page.click("button[type='submit']")
            
            # 2. Projects Page
            print("Waiting for redirect to projects page...")
            await page.wait_for_url("http://localhost:3000/projects", timeout=10000)
            print("Successfully logged in.")
            
            # 3. Create Audit
            print("Filling out new audit form...")
            await page.fill("input[type='url']", "https://example.com/about")
            await page.click("button:has-text('Start Audit')")
            
            # 4. Wait for redirect to Audit Page
            print("Waiting for redirect to Audit Page...")
            await page.wait_for_url("**/audits/**", timeout=10000)
            print(f"Redirected to Audit Page: {page.url}")
            
            # 5. Wait for Audit to process
            print("Waiting for audit to complete (SSE streaming)...")
            
            # Give it up to 60 seconds for the celery worker to process
            await page.wait_for_timeout(5000)
            
            # Check for findings
            html = await page.content()
            if "No findings" in html:
                print("SUCCESS: Audit page loaded, but no findings generated.")
            elif "Loading findings..." in html:
                print("WARNING: Findings are still loading after 5s.")
            else:
                rows = await page.locator("tbody tr").count()
                print(f"SUCCESS: Audit generated {rows} table rows (findings).")
                
        except Exception as e:
            print(f"ERROR: {e}")
            await page.screenshot(path="error.png")
            print("Saved screenshot to error.png")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
