from src.storage.db import connect, upsert_item
from src.storage.models import InformationItem
from src.utils.text_utils import normalize_url


def test_url_normalization():
    assert normalize_url("/a/b#top", "https://EXAMPLE.com/root/") == "https://example.com/a/b"


def test_url_dedup_and_content_change_detection(tmp_path):
    conn = connect(str(tmp_path / "db.sqlite3"))
    item = InformationItem(
        title="新的研究结果",
        url="https://example.com/a",
        source_name="测试源",
        source_url="https://example.com",
        group="学术",
        content="version one",
        content_hash="hash-1",
    )
    assert upsert_item(conn, item) == "new"
    assert upsert_item(conn, item) == "unchanged"

    item.content = "version two"
    item.content_hash = "hash-2"
    assert upsert_item(conn, item) == "changed"

    count = conn.execute("SELECT COUNT(*) FROM information_items").fetchone()[0]
    assert count == 1


def test_title_source_dedup_when_url_missing(tmp_path):
    conn = connect(str(tmp_path / "db.sqlite3"))
    item = InformationItem(
        title="一条没有 URL 的信息",
        url=None,
        source_name="测试源",
        source_url="https://example.com",
        content_hash="hash-1",
    )
    assert upsert_item(conn, item) == "new"
    assert upsert_item(conn, item) == "unchanged"
    count = conn.execute("SELECT COUNT(*) FROM information_items").fetchone()[0]
    assert count == 1
