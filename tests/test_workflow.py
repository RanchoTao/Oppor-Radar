from pathlib import Path

import yaml

DATA_WORKFLOWS = (".github/workflows/daily.yml", ".github/workflows/refresh.yml")


def test_data_workflows_persist_database_outside_main():
    for path in DATA_WORKFLOWS:
        text = Path(path).read_text(encoding="utf-8")
        restore = text.index("scripts/db_store.sh restore")
        run = text.index("python -m src.scheduler.run_daily")
        save = text.index("scripts/db_store.sh save")
        assert restore < run < save, path
        assert "opportunities.sqlite3" not in text, path
        assert "git pull --rebase origin main" in text, path


def test_data_workflows_share_one_concurrency_group_and_model():
    groups = set()
    for path in DATA_WORKFLOWS:
        workflow = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        groups.add(workflow["concurrency"]["group"])
        assert workflow["concurrency"]["cancel-in-progress"] is False
        assert "DEEPSEEK_MODEL: deepseek-flash" in Path(path).read_text(encoding="utf-8")
    assert len(groups) == 1


def test_pages_deploys_after_every_workflow_that_commits_an_edition():
    pages = yaml.safe_load(Path(".github/workflows/pages.yml").read_text(encoding="utf-8"))
    # PyYAML parses the bare key "on" as boolean True.
    triggers = pages.get("on", pages.get(True))
    listened = set(triggers["workflow_run"]["workflows"])
    for path in DATA_WORKFLOWS:
        name = yaml.safe_load(Path(path).read_text(encoding="utf-8"))["name"]
        assert name in listened, name
