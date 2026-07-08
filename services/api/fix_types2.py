import os
import re

# 1. test_crawler.py
path = 'tests/test_crawler.py'
content = open(path).read()
content = content.replace('assert "Forbidden IP range" in res.error', 'assert "Forbidden IP range" in (res.error or "")')
open(path, 'w').write(content)

# 2. discovery.py
path = 'app/crawler/discovery.py'
content = open(path).read()
content = content.replace('session.get(sitemap_url, timeout=10)', 'session.get(sitemap_url, timeout=aiohttp.ClientTimeout(total=10))')
open(path, 'w').write(content)

# 3. fetcher.py
path = 'app/crawler/fetcher.py'
content = open(path).read()
content = content.replace('session.get(url, timeout=15', 'session.get(url, timeout=aiohttp.ClientTimeout(total=15)')
open(path, 'w').write(content)

# 4. robots.py
path = 'app/crawler/robots.py'
content = open(path).read()
content = content.replace('session.get(robots_url, timeout=5)', 'session.get(robots_url, timeout=aiohttp.ClientTimeout(total=5))')
# Fix the except block for rp.allow_all
content = content.replace('except Exception as e:\n        logger.warning(f"Error fetching robots.txt for {parsed.netloc}: {e}")\n        rp.allow_all = True\n        return rp', 'except Exception as e:\n        logger.warning(f"Error fetching robots.txt for {parsed.netloc}: {e}")\n        return rp')
open(path, 'w').write(content)

# 5. deps.py
path = 'app/core/deps.py'
content = open(path).read()
content = content.replace('lambda cls: cls.org_id == org_id,', 'lambda cls: cls.org_id == org_id,  # type: ignore')
content = content.replace('def _add_org_isolation(execute_state: orm.ORMExecuteState):', 'def _add_org_isolation(execute_state: orm.ORMExecuteState):  # type: ignore')
content = content.replace('if not execute_state.execution_options.get("include_loader_criteria", True):', 'if not getattr(execute_state.execution_options, "get", dict().get)("include_loader_criteria", True):  # type: ignore')
open(path, 'w').write(content)

print("Done")
