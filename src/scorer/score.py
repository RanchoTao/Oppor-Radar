from __future__ import annotations

from src.storage.models import Opportunity
from src.utils.text_utils import contains_any
from src.utils.time_utils import is_before_today

TARGETS = ["清华", "北大", "北京大学", "人大", "中国人民大学", "中科院", "BIMSA"]
UNDERGRAD = ["本科生", "高年级本科生", "大三", "大二", "本科"]
MENTOR = ["导师", "课题组", "科研", "项目", "实验室", "RA"]
BEIJING_ONLINE = ["北京", "线上", "清华", "北大", "人大", "雁栖湖"]


def score_opportunity(opp: Opportunity, keywords: dict, scoring: dict) -> Opportunity:
    rules = scoring["rules"]
    text = f"{opp.title} {opp.summary} {opp.raw_text} {opp.source_name}"
    score = 0
    reasons: list[str] = []
    if contains_any(text, keywords.get("core", [])):
        score += rules["core_match"]; reasons.append("命中 AI/机器学习核心关键词")
    if contains_any(text, keywords.get("math", [])):
        score += rules["math_match"]; reasons.append("命中数学相关关键词")
    if contains_any(text, keywords.get("opportunity", [])):
        score += rules["opportunity_match"]; reasons.append("命中机会类型关键词")
    if contains_any(opp.source_name, TARGETS):
        score += rules["target_institution"]; reasons.append("来源属于目标机构")
    if contains_any(text, UNDERGRAD):
        score += rules["undergraduate_friendly"]; reasons.append("对本科生较友好")
    if contains_any(text, MENTOR):
        score += rules["mentor_or_research"]; reasons.append("包含导师/科研/项目线索")
    if contains_any(text, BEIJING_ONLINE):
        score += rules["beijing_or_online"]; reasons.append("地点或来源便于关注")
    if opp.deadline:
        score += rules["has_deadline"]; reasons.append("包含截止日期")
    if contains_any(text, keywords.get("negative", [])):
        score += rules["negative_match"]; reasons.append("命中负面关键词")
    expired = "已截止" in text or is_before_today(opp.deadline)
    opp.score = score
    opp.category = "X" if expired else classify_score(score, scoring)
    if expired:
        reasons.append("已截止或截止日期早于今天")
    opp.reason = "；".join(reasons) or "未命中明显推荐规则"
    return opp


def classify_score(score: int, scoring: dict) -> str:
    classes = scoring["classes"]
    if score >= classes["A"]:
        return "A"
    if score >= classes["B"]:
        return "B"
    if score >= classes["C"]:
        return "C"
    return "X"
