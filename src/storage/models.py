from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InformationItem:
    """A generic piece of information discovered from a subscribed source.

    The product is no longer modeled around application opportunities.  Academic
    deadlines are still preserved as optional metadata because they are useful for
    some sources, but ranking is driven by user relevance and information value.
    """

    title: str
    url: str | None
    source_name: str
    source_url: str
    group: str = "未分组"

    publish_date: str | None = None
    deadline: str | None = None
    event_date: str | None = None
    location: str | None = None

    summary: str = ""
    content: str = ""
    raw_text: str = ""
    content_hash: str = ""

    topics: list[str] = field(default_factory=list)
    importance: float = 0.0
    relevance: float = 0.0
    novelty: float = 0.0
    keep: bool = True
    reason: str = ""
    action: str = ""
    time_sensitive: bool = False

    first_seen_at: str | None = None
    last_seen_at: str | None = None
    changed_at: str | None = None

    @property
    def value_score(self) -> float:
        """Stable display/ranking score without resurrecting the old A/B/C/X model."""
        return round(0.4 * self.relevance + 0.35 * self.importance + 0.25 * self.novelty, 4)


# Transitional import compatibility for modules/tests that still import Opportunity.
# New code should use InformationItem directly.
Opportunity = InformationItem
