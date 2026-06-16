from __future__ import annotations

from src.storage.models import Opportunity


def enrich_with_llm_stub(opp: Opportunity) -> Opportunity:
    """Reserved extension point for future LLM-based extraction."""
    return opp
