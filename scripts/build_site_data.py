from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "config" / "sources.yaml"
REPORTS_DIR = ROOT / "data" / "reports"
DOCS_DATA_DIR = ROOT / "docs" / "data"
DOCS_REPORTS_DIR = ROOT / "docs" / "reports"


def main() -> None:
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    sources = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8")) or []
    (DOCS_DATA_DIR / "sources.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    reports = sorted(REPORTS_DIR.glob("????-??-??.md"), reverse=True)
    manifest = []
    active_names = set()

    for report in reports:
        md_target = DOCS_REPORTS_DIR / report.name
        shutil.copyfile(report, md_target)
        active_names.add(report.name)

        json_source = report.with_suffix(".json")
        json_filename = None
        if json_source.exists():
            json_target = DOCS_REPORTS_DIR / json_source.name
            shutil.copyfile(json_source, json_target)
            active_names.add(json_source.name)
            json_filename = json_source.name

        manifest.append(
            {
                "date": report.stem,
                "filename": report.name,
                "json_filename": json_filename,
                "format": "personalized-v2" if json_filename else "legacy-v1",
            }
        )

    for stale in DOCS_REPORTS_DIR.glob("*.*"):
        if stale.suffix in {".md", ".json"} and stale.name not in active_names:
            stale.unlink()

    (DOCS_DATA_DIR / "reports.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
