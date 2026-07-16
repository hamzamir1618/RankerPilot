def get_shingles(text: str, k: int = 5) -> set:
    words = text.lower().split()
    return set(" ".join(words[i:i+k]) for i in range(len(words) - k + 1))

def jaccard_similarity(text1: str | None, text2: str | None) -> float:
    """
    Computes Jaccard similarity of character-level or word-level shingles.
    """
    if not text1 or not text2:
        return 0.0
    s1 = get_shingles(text1)
    s2 = get_shingles(text2)
    if not s1 or not s2:
        return 0.0
    return len(s1.intersection(s2)) / len(s1.union(s2))
