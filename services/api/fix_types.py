import os

# 1. test_auth.py
path = 'tests/test_auth.py'
content = open(path).read()
content = content.replace('cookies={"refresh_token": refresh_cookie}', 'cookies={"refresh_token": refresh_cookie or ""}')
content = content.replace('cookies={"refresh_token": new_refresh_cookie}', 'cookies={"refresh_token": new_refresh_cookie or ""}')
open(path, 'w').write(content)

# 2. crawler/discovery.py
path = 'app/crawler/discovery.py'
content = open(path).read()
content = content.replace('ClientSession(timeout=10)', 'ClientSession(timeout=aiohttp.ClientTimeout(total=10))')
open(path, 'w').write(content)

# 3. crawler/fetcher.py
path = 'app/crawler/fetcher.py'
content = open(path).read()
content = content.replace('BeautifulSoup(html, "lxml")', 'BeautifulSoup(html if isinstance(html, str) else html.decode("utf-8", errors="replace"), "lxml")')
content = content.replace('parsed.hostname', 'parsed.hostname or ""')
content = content.replace('ClientSession(timeout=15)', 'ClientSession(timeout=aiohttp.ClientTimeout(total=15))')
open(path, 'w').write(content)

# 4. crawler/robots.py
import re
path = 'app/crawler/robots.py'
content = open(path).read()
content = content.replace('ClientSession(timeout=5)', 'ClientSession(timeout=aiohttp.ClientTimeout(total=5))')
lines = content.split('\n')
lines = [l for l in lines if 'rp.allow_all = True' not in l]
open(path, 'w').write('\n'.join(lines))

# 5. crawler/validator.py
path = 'app/crawler/validator.py'
content = open(path).read()
content = content.replace('return f"{ip}:{port}" if port else ip', 'return f"{ip}:{port}" if port else str(ip)')
open(path, 'w').write(content)

# 6. workers/pipelines.py
path = 'app/workers/pipelines.py'
content = open(path).read()
content = content.replace('audit.project_id', '(audit.project_id if audit else None)')
open(path, 'w').write(content)

print("Done")
