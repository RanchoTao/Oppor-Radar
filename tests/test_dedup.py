from src.storage.db import connect, upsert_opportunity
from src.storage.models import Opportunity
from src.utils.text_utils import normalize_url


def test_url_normalization():
    assert normalize_url("/a/b#top", "https://EXAMPLE.com/root/") == "https://example.com/a/b"


def test_url_dedup_updates_last_seen(tmp_path):
    conn = connect(str(tmp_path / "db.sqlite3"))
    opp = Opportunity(title="AI 夏令营", url="https://example.com/a", source_name="测试源", source_url="https://example.com")
    assert upsert_opportunity(conn, opp) is True
    assert upsert_opportunity(conn, opp) is False
    count = conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
    assert count == 1


def test_title_source_dedup_when_url_missing(tmp_path):
    conn = connect(str(tmp_path / "db.sqlite3"))
    opp = Opportunity(title="AI 夏令营", url=None, source_name="测试源", source_url="https://example.com")
    assert upsert_opportunity(conn, opp) is True
    assert upsert_opportunity(conn, opp) is False
    count = conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
    assert count == 1
