from app.agents.base import BaseAgent, AuditContext

class BacklinksAgent(BaseAgent):
    async def run(self, ctx: AuditContext) -> list[dict]:
        from app.integrations.dataforseo import get_backlinks_summary
        
        findings = []
        domain = ctx.root_url.replace("https://", "").replace("http://", "").split("/")[0]
        
        try:
            summary = await get_backlinks_summary(domain)
            if not summary:
                return []

            toxic_ratio = summary.get("toxic_ratio", 0)
            if toxic_ratio > 0.1:
                findings.append(self.create_finding(
                    ctx,
                    check_id="backlinks_toxic_ratio",
                    status="fail",
                    severity="high",
                    category="technical",
                    title="High Toxic Backlink Ratio",
                    effort="one_month",
                    evidence={"toxic_ratio": toxic_ratio},
                    fix="Disavow toxic referring domains using Google Search Console."
                ))
            else:
                findings.append(self.create_finding(
                    ctx,
                    check_id="backlinks_toxic_ratio",
                    status="pass",
                    category="technical",
                    title="Healthy Backlink Profile",
                    evidence={"toxic_ratio": toxic_ratio}
                ))

            lost_links = summary.get("lost_links_30d", 0)
            if lost_links > 50:
                findings.append(self.create_finding(
                    ctx,
                    check_id="backlinks_lost",
                    status="fail", # Treat warning as low severity fail for action plan
                    severity="low",
                    category="technical",
                    title="High Number of Lost Backlinks",
                    effort="one_month",
                    evidence={"lost_links_30d": lost_links},
                    fix="Investigate lost links and attempt link reclamation outreach."
                ))

        except Exception:
            pass

        return findings
