from __future__ import annotations

from urllib.parse import urlparse


class RegistryValidationError(ValueError):
    pass


def _nonempty_string(value, field: str, max_length: int = 240) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegistryValidationError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > max_length:
        raise RegistryValidationError(f"{field} is too long")
    return value


def validate_groups(groups) -> list[dict]:
    if not isinstance(groups, list):
        raise RegistryValidationError("groups must be a list")
    if len(groups) > 100:
        raise RegistryValidationError("too many groups")

    result = []
    names = set()
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            raise RegistryValidationError(f"groups[{index}] must be an object")
        name = _nonempty_string(group.get("name"), f"groups[{index}].name", 80)
        if name in names:
            raise RegistryValidationError(f"duplicate group: {name}")
        names.add(name)
        result.append(
            {
                "name": name,
                "order": int(group.get("order", (index + 1) * 10)),
                "enabled": bool(group.get("enabled", True)),
            }
        )
    return result


def _string_list(value, field: str, limit: int = 40) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RegistryValidationError(f"{field} must be a list")
    if len(value) > limit:
        raise RegistryValidationError(f"{field} has too many values")
    return [_nonempty_string(item, field, 120) for item in value]


def validate_sources(sources, groups: list[dict] | None = None) -> list[dict]:
    if not isinstance(sources, list):
        raise RegistryValidationError("sources must be a list")
    if len(sources) > 1000:
        raise RegistryValidationError("too many sources")

    group_names = {group["name"] for group in (groups or [])}
    names = set()
    urls = set()
    result = []

    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise RegistryValidationError(f"sources[{index}] must be an object")
        name = _nonempty_string(source.get("name"), f"sources[{index}].name")
        url = _nonempty_string(source.get("url"), f"sources[{index}].url", 2000)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RegistryValidationError(f"invalid source URL: {url}")
        if name in names:
            raise RegistryValidationError(f"duplicate source name: {name}")
        if url in urls:
            raise RegistryValidationError(f"duplicate source URL: {url}")
        names.add(name)
        urls.add(url)

        group = str(source.get("group") or "未分组").strip()
        if group_names and group != "未分组" and group not in group_names:
            raise RegistryValidationError(f"unknown group for {name}: {group}")

        result.append(
            {
                "name": name,
                "url": url,
                "group": group,
                "enabled": bool(source.get("enabled", True)),
                "tags": _string_list(source.get("tags"), f"sources[{index}].tags"),
                "watch": _string_list(source.get("watch"), f"sources[{index}].watch"),
                "max_items": max(1, min(100, int(source.get("max_items", 24)))),
                "max_detail_items": max(0, min(100, int(source.get("max_detail_items", 16)))),
                "fetch_details": bool(source.get("fetch_details", True)),
            }
        )
    return result


def validate_profile(profile) -> dict:
    if not isinstance(profile, dict):
        raise RegistryValidationError("profile must be an object")
    result = dict(profile)
    for key in ("interests", "high_priority_signals", "low_priority_signals"):
        if key in result:
            result[key] = _string_list(result[key], key, limit=100)
    if "language" in result:
        result["language"] = _nonempty_string(result["language"], "language", 40)
    if "timezone" in result:
        result["timezone"] = _nonempty_string(result["timezone"], "timezone", 80)
    editorial = result.get("editorial_preferences")
    if editorial is not None and not isinstance(editorial, dict):
        raise RegistryValidationError("editorial_preferences must be an object")
    return result
