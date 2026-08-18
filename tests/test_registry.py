import base64

import pytest
import yaml

from api.registry import prepare_payload
from src.registry.github_store import GithubRegistryStore
from src.registry.validation import RegistryValidationError, validate_groups, validate_sources


def test_registry_accepts_groups_and_domain_neutral_sources():
    groups = validate_groups([
        {"name": "学术", "order": 10},
        {"name": "金融", "order": 20},
    ])
    sources = validate_sources(
        [
            {
                "name": "Example Macro",
                "url": "https://example.com/macro",
                "group": "金融",
                "tags": ["宏观"],
                "watch": ["利率"],
            }
        ],
        groups,
    )
    assert sources[0]["group"] == "金融"
    assert sources[0]["max_items"] == 24


def test_registry_rejects_unknown_group_and_invalid_url():
    groups = validate_groups([{"name": "学术"}])
    with pytest.raises(RegistryValidationError):
        validate_sources(
            [{"name": "Bad", "url": "javascript:alert(1)", "group": "其他"}],
            groups,
        )


def test_prepare_payload_validates_sources_against_new_groups():
    current = {
        "groups": [{"name": "旧组", "order": 10, "enabled": True}],
        "sources": [],
        "profile": {},
    }
    payload = prepare_payload(
        {
            "groups": [{"name": "AI / 科技", "order": 10}],
            "sources": [
                {
                    "name": "Example AI",
                    "url": "https://example.com/ai",
                    "group": "AI / 科技",
                }
            ],
        },
        current,
    )
    assert payload["sources"][0]["group"] == "AI / 科技"


def test_github_store_reads_and_writes_yaml(monkeypatch):
    calls = []

    class Response:
        def __init__(self, body):
            self.body = body
        def raise_for_status(self):
            return None
        def json(self):
            return self.body

    encoded = base64.b64encode(b"- name: \xe5\xad\xa6\xe6\x9c\xaf\n  order: 10\n").decode("ascii")

    def fake_get(url, headers, params, timeout):
        calls.append(("get", url, params))
        return Response({"sha": "old-sha", "content": encoded})

    def fake_put(url, headers, json, timeout):
        calls.append(("put", url, json))
        decoded = base64.b64decode(json["content"]).decode("utf-8")
        assert yaml.safe_load(decoded)[0]["name"] == "学术"
        return Response({"commit": {"sha": "commit-sha"}})

    monkeypatch.setattr("src.registry.github_store.requests.get", fake_get)
    monkeypatch.setattr("src.registry.github_store.requests.put", fake_put)

    store = GithubRegistryStore(token="token", repo="owner/repo", branch="main")
    file = store.read_yaml("config/groups.yaml")
    assert file.content[0]["name"] == "学术"
    assert store.write_yaml("config/groups.yaml", file.content, file.sha, "update") == "commit-sha"
    assert calls[0][0] == "get"
    assert calls[1][0] == "put"
