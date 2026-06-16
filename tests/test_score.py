from src.scorer.score import classify_score, score_opportunity
from src.storage.models import Opportunity


def scoring():
    return {"rules": {"core_match": 35, "math_match": 15, "opportunity_match": 20, "target_institution": 15, "undergraduate_friendly": 20, "mentor_or_research": 15, "beijing_or_online": 5, "has_deadline": 10, "expired": -100, "negative_match": -80}, "classes": {"A": 70, "B": 45, "C": 20, "X": -999}}


def keywords():
    return {"core": ["AI", "人工智能"], "math": ["数学"], "opportunity": ["夏令营", "RA"], "negative": ["博士后"]}


def test_keyword_scoring_a_class():
    opp = Opportunity(title="AI 数学 夏令营招收本科生", url="https://x.test/a", source_name="清华", source_url="https://x.test", summary="导师科研项目 北京", deadline="2099-01-01")
    scored = score_opportunity(opp, keywords(), scoring())
    assert scored.score >= 70
    assert scored.category == "A"


def test_classification_thresholds():
    assert classify_score(70, scoring()) == "A"
    assert classify_score(45, scoring()) == "B"
    assert classify_score(20, scoring()) == "C"
    assert classify_score(19, scoring()) == "X"
