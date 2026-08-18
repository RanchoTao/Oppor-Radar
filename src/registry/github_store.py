from __future__ import annotations

import base64
import os
from dataclasses import dataclass

import requests
import yaml


@dataclass
class GithubFile:
    path: str
    sha: str
    content: object


class GithubRegistryStore:
    def __init__(
        self,
        token: str | None = None,
        repo: str | None = None,
        branch: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.token = (token or os.getenv("OPPOR_GITHUB_TOKEN", "")).strip()
        self.repo = (repo or os.getenv("OPPOR_GITHUB_REPO", "RanchoTao/Oppor-Radar")).strip()
        self.branch = (branch or os.getenv("OPPOR_GITHUB_BRANCH", "main")).strip()
        self.timeout = timeout
        if not self.token:
            raise RuntimeError("OPPOR_GITHUB_TOKEN is not configured")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _url(self, path: str) -> str:
        return f"https://api.github.com/repos/{self.repo}/contents/{path}"

    def read_yaml(self, path: str) -> GithubFile:
        response = requests.get(
            self._url(path),
            headers=self.headers,
            params={"ref": self.branch},
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        raw = base64.b64decode(body["content"]).decode("utf-8")
        return GithubFile(path=path, sha=body["sha"], content=yaml.safe_load(raw))

    def write_yaml(self, path: str, value, sha: str, message: str) -> str:
        raw = yaml.safe_dump(
            value,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=120,
        )
        response = requests.put(
            self._url(path),
            headers={**self.headers, "Content-Type": "application/json"},
            json={
                "message": message,
                "content": base64.b64encode(raw.encode("utf-8")).decode("ascii"),
                "sha": sha,
                "branch": self.branch,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["commit"]["sha"]

    def read_registry(self) -> dict:
        groups = self.read_yaml("config/groups.yaml")
        sources = self.read_yaml("config/sources.yaml")
        profile = self.read_yaml("config/profile.yaml")
        return {
            "groups": groups.content or [],
            "sources": sources.content or [],
            "profile": profile.content or {},
            "revision": {
                "groups": groups.sha,
                "sources": sources.sha,
                "profile": profile.sha,
            },
        }

    def write_registry(self, payload: dict, message: str = "chore: update Oppor Radar registry") -> dict:
        current = self.read_registry()
        commits = []
        for key, path in (
            ("groups", "config/groups.yaml"),
            ("sources", "config/sources.yaml"),
            ("profile", "config/profile.yaml"),
        ):
            if key not in payload:
                continue
            commit = self.write_yaml(
                path,
                payload[key],
                current["revision"][key],
                f"{message}: {key}",
            )
            commits.append(commit)
            # Re-read before the next write so branch state and file SHA remain fresh.
            current = self.read_registry()
        return {"commits": commits, "registry": self.read_registry()}
