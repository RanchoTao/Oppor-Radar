from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "config" / "sources.yaml"
GROUPS_PATH = ROOT / "config" / "groups.yaml"
REPORTS_DIR = ROOT / "data" / "reports"
DOCS_DATA_DIR = ROOT / "docs" / "data"
DOCS_REPORTS_DIR = ROOT / "docs" / "reports"


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    sources = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8")) or []
    groups = yaml.safe_load(GROUPS_PATH.read_text(encoding="utf-8")) or []
    _write_json(DOCS_DATA_DIR / "sources.json", sources)
    _write_json(DOCS_DATA_DIR / "groups.json", groups)

    manifest = []
    active_names: set[str] = set()
    latest_public_status = {
        "configured_sources": len([s for s in sources if s.get("enabled", True)]),
        "healthy_sources": None,
        "new_items": 0,
        "selected_items": 0,
        "last_updated_at": None,
    }

    # JSON schema v2 is the source of truth. Legacy A/B/C/X Markdown is deliberately
    # not published into the product UI anymore.
    for json_source in sorted(REPORTS_DIR.glob("????-??-??.json"), reverse=True):
        try:
            payload = json.loads(json_source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("schema_version") != 2:
            continue

        stem = json_source.stem
        files = {}
        for suffix in (".json", ".md", ".tex", ".pdf"):
            source = REPORTS_DIR / f"{stem}{suffix}"
            if source.exists():
                target = DOCS_REPORTS_DIR / source.name
                shutil.copyfile(source, target)
                active_names.add(source.name)
                files[suffix.lstrip(".")] = source.name

        manifest.append({"date": stem, "files": files})
        if len(manifest) == 1:
            latest_public_status.update(payload.get("metrics") or {})

    for stale in DOCS_REPORTS_DIR.glob("*.*"):
        if stale.suffix in {".md", ".json", ".tex", ".pdf"} and stale.name not in active_names:
            stale.unlink()

    _write_json(DOCS_DATA_DIR / "reports.json", manifest)
    _write_json(DOCS_DATA_DIR / "status.json", latest_public_status)


if __name__ == "__main__":
    main()
