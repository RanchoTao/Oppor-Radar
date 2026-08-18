from pathlib import Path


def test_daily_workflow_force_adds_ignored_sqlite_database():
    workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

    assert "git add -f data/opportunities.sqlite3" in workflow
    assert "permissions:\n  contents: write" in workflow
