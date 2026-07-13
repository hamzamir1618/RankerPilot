import pytest
from hypothesis import given, strategies as st
from typing import List, Dict
import math

from app.scoring.aggregate import calculate_category_score, calculate_site_score
from app.scoring.weights import get_category_weights, WEIGHTS, LOCAL_SERVICE_WEIGHTS
from app.scoring.action_plan import get_action_plan_sort_key
from app.models.models import FindingStatusEnum, IndustryEnum

def test_severity_multipliers():
    """Verify that different severities produce correctly weighted fail scores."""
    # Base: 10 passes. Score = 100 * (10 / 10) = 100
    score_perfect = calculate_category_score(10, {})
    assert score_perfect == 100.0

    # 10 passes, 1 critical fail. Weighted fails = 4. Score = 100 * (10 / 14) = 71.428...
    score_crit = calculate_category_score(10, {"critical": 1})
    assert math.isclose(score_crit, 71.42857142857143)

    # 10 passes, 1 high fail. Weighted fails = 2.5. Score = 100 * (10 / 12.5) = 80.0
    score_high = calculate_category_score(10, {"high": 1})
    assert math.isclose(score_high, 80.0)

    # 10 passes, 1 medium fail. Weighted fails = 1.5. Score = 100 * (10 / 11.5) = 86.956...
    score_med = calculate_category_score(10, {"medium": 1})
    assert math.isclose(score_med, 86.95652173913044)

    # 10 passes, 1 low fail. Weighted fails = 1.0. Score = 100 * (10 / 11.0) = 90.909...
    score_low = calculate_category_score(10, {"low": 1})
    assert math.isclose(score_low, 90.9090909090909)

def test_industry_weight_overrides():
    """Verify that industry overrides work properly."""
    saas_weights = get_category_weights(IndustryEnum.saas)
    assert saas_weights == WEIGHTS
    assert "local" not in saas_weights

    local_weights = get_category_weights(IndustryEnum.local_service)
    assert local_weights == LOCAL_SERVICE_WEIGHTS
    assert local_weights["onpage"] == 0.12
    assert local_weights["local"] == 0.08

def test_action_plan_sorting():
    """Verify that action plan sort key ranks correctly: severity (asc), traffic (desc), effort (asc)."""
    # lower tuple = higher priority
    k1 = get_action_plan_sort_key("critical", "immediate", 0.5)
    k2 = get_action_plan_sort_key("critical", "immediate", 0.1) # Less traffic
    k3 = get_action_plan_sort_key("high", "immediate", 0.9)
    k4 = get_action_plan_sort_key("high", "backlog", 0.9)
    
    # critical > high
    assert k1 < k3
    # same severity, effort -> traffic matters (higher traffic = smaller negated number = sorts first)
    assert k1 < k2
    # same severity, traffic -> effort matters (immediate < backlog)
    assert k3 < k4

# Generate a finding structure: status, category, severity
finding_strategy = st.fixed_dictionaries({
    "status": st.sampled_from(["pass", "fail"]),
    "category": st.sampled_from(list(WEIGHTS.keys())),
    "severity": st.sampled_from(["critical", "high", "medium", "low"])
})

@given(st.lists(finding_strategy, min_size=1, max_size=100))
def test_monotonicity(findings: List[Dict]):
    """
    Property-based test: For any findings set, converting any single 'fail' finding to a 'pass'
    (holding everything else constant) must never decrease the resulting site score.
    """
    def compute_score(findings_list):
        cat_stats = {cat: {"passes": 0, "severity_counts": {}} for cat in WEIGHTS.keys()}
        for f in findings_list:
            cat = f["category"]
            if f["status"] == "pass":
                cat_stats[cat]["passes"] += 1
            else:
                sev = f["severity"]
                cat_stats[cat]["severity_counts"][sev] = cat_stats[cat]["severity_counts"].get(sev, 0) + 1
                
        category_scores = {}
        for cat, stats in cat_stats.items():
            # If no checks ran, calculate_category_score handles it (returns 100.0)
            category_scores[cat] = calculate_category_score(stats["passes"], stats["severity_counts"])
            
        return calculate_site_score(category_scores, WEIGHTS)

    base_score = compute_score(findings)
    
    for i in range(len(findings)):
        if findings[i]["status"] == "fail":
            # Create a modified copy where this fail is now a pass
            modified_findings = [f.copy() for f in findings]
            modified_findings[i]["status"] = "pass"
            
            new_score = compute_score(modified_findings)
            
            # The new score MUST be greater than or equal to the base score
            assert new_score >= base_score, f"Monotonicity violated! Base: {base_score}, New: {new_score}"
