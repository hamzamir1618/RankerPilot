from typing import Dict, List, Tuple

SEVERITY_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

EFFORT_RANK = {
    "immediate": 0,
    "one_week": 1,
    "one_month": 2,
    "backlog": 3,
}

def compute_internal_pagerank(site_graph: Dict[str, List[str]], iterations: int = 20, d: float = 0.85) -> Dict[str, float]:
    """
    Computes a simple iterative PageRank over the internal link graph.
    site_graph: dict mapping url -> list of outbound urls.
    Returns: dict mapping url -> PageRank score.
    """
    if not site_graph:
        return {}
        
    # Initialize PageRank
    pr = {url: 1.0 for url in site_graph.keys()}
    
    # We also need to know all nodes. The graph keys should contain all known pages.
    # Outbound links might point to pages not in keys (e.g. external). We ignore them.
    nodes = set(site_graph.keys())
    
    # Precompute in-links for each node to optimize the loop
    in_links: Dict[str, List[str]] = {node: [] for node in nodes}
    out_degree: Dict[str, int] = {node: 0 for node in nodes}
    
    for u, edges in site_graph.items():
        for v in edges:
            if v in nodes:
                in_links[v].append(u)
                out_degree[u] += 1
                
    N = len(nodes)
    if N == 0:
        return {}
        
    base_pr = 1.0 - d
    
    for _ in range(iterations):
        new_pr = {}
        for node in nodes:
            sum_in = sum(pr[in_node] / out_degree[in_node] for in_node in in_links[node] if out_degree[in_node] > 0)
            new_pr[node] = base_pr + d * sum_in
        pr = new_pr
        
    return pr

def get_action_plan_sort_key(
    severity: str | None, 
    effort: str | None, 
    page_rank: float | None
) -> Tuple[int, float, int]:
    """
    Returns a sort key tuple: (severity_rank, traffic_weight (desc), effort_rank).
    Python sorts tuples lexicographically, so we negate traffic_weight for desc sorting.
    """
    s_rank = SEVERITY_RANK.get(severity, 4) if severity else 4
    e_rank = EFFORT_RANK.get(effort, 4) if effort else 4
    
    # traffic_weight is desc, so negate it.
    t_weight = -(page_rank or 0.0)
    
    return (s_rank, t_weight, e_rank)
