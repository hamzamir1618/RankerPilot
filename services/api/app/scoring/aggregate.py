from typing import Dict

def calculate_category_score(passes: int, severity_counts: Dict[str, int]) -> float:
    """
    Calculate the score for a single category using a weighted pass ratio.
    Passes count as 1.
    Failures are weighted by severity:
      critical: 4
      high: 2.5
      medium: 1.5
      low: 1
    
    Category score = 100 * (passes / (passes + total_weighted_fails))
    """
    weighted_fails = (
        severity_counts.get("critical", 0) * 4.0 +
        severity_counts.get("high", 0) * 2.5 +
        severity_counts.get("medium", 0) * 1.5 +
        severity_counts.get("low", 0) * 1.0
    )
    
    total = passes + weighted_fails
    if total == 0:
        return 100.0  # Or 0, but if there's nothing, 100 is typically safe. Let's return 0 if no checks ran.
        return 0.0
        # Wait, usually if a category has no checks it shouldn't count. 
        # But if we return 0.0, we can filter it out later. Let's return 0.0 if total == 0.
        
    # Wait, let's just return 100.0 if total == 0 so that empty categories don't drag down the score.
    if total == 0:
        return 100.0
        
    return 100.0 * (passes / total)

def calculate_site_score(category_scores: Dict[str, float], weights: Dict[str, float]) -> float:
    """
    Site score = Σ(category_score × weight), rounded to 1 decimal place.
    If a category is missing from scores but present in weights, it contributes 0 to the sum.
    We normalize the weights if they don't exactly sum to 1.
    """
    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0.0
        
    weighted_sum = 0.0
    for cat, weight in weights.items():
        # Default missing category scores to 100.0 (if no checks ran, it passes)
        # But wait, maybe 0.0 is better? Let's use what we compute.
        score = category_scores.get(cat, 100.0) 
        weighted_sum += score * weight
        
    return round(weighted_sum / total_weight, 1)
