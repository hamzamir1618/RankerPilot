def compute_opportunity_score(volume: int | None, difficulty: float | None, position: int | None) -> float:
    """
    Computes a keyword opportunity score (0.0 to 100.0).
    
    Weights:
    - Volume: 40% (High volume is better, maxes out at 10,000 for local/SaaS typical queries)
    - Difficulty: 30% (Lower difficulty is better)
    - Position: 30% (Positions 8-20 are heavily prioritized as 'Quick Wins')
    """
    vol = volume or 0
    diff = difficulty or 100.0
    
    # 1. Volume Score (max 100)
    # Logarithmic-like scaling using an aggressive cap or simple linear up to 10k
    vol_score = min(vol / 10000.0, 1.0) * 100.0
    if vol > 10000:
        vol_score = 100.0
        
    # 2. Difficulty Score (max 100)
    # Difficulty is usually 0-100. Lower is better.
    diff_score = 100.0 - diff
    
    # 3. Position Score (max 100)
    # 8-20 is "striking distance" / Quick win -> max points
    # 4-7 is good but requires more effort to push to top 3 -> medium points
    # 1-3 is already winning -> low opportunity to improve
    # 21-50 is secondary striking -> lower points
    # >50 is too far -> very low points
    pos = position or 0
    if pos == 0:
        pos_score = 20.0 # Unranked
    elif 1 <= pos <= 3:
        pos_score = 10.0
    elif 4 <= pos <= 7:
        pos_score = 50.0
    elif 8 <= pos <= 20:
        pos_score = 100.0
    elif 21 <= pos <= 50:
        pos_score = 60.0
    else:
        pos_score = 30.0
        
    # Calculate weighted score
    score = (vol_score * 0.40) + (diff_score * 0.30) + (pos_score * 0.30)
    
    return round(score, 2)
