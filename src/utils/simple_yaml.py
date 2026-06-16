from __future__ import annotations

import ast


def safe_load(text: str):
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith('#')]
    if any(ln.startswith('- ') for ln in lines):
        items = []
        cur = None
        for ln in lines:
            if ln.startswith('- '):
                if cur:
                    items.append(cur)
                cur = {}
                key, val = ln[2:].split(':', 1)
                cur[key.strip()] = _val(val.strip())
            elif cur is not None and ':' in ln:
                key, val = ln.strip().split(':', 1)
                cur[key.strip()] = _val(val.strip())
        if cur:
            items.append(cur)
        return items

    root = {}
    cur_key = None
    for ln in lines:
        if not ln.startswith(' ') and ':' in ln:
            key, val = ln.split(':', 1)
            cur_key = key.strip()
            root[cur_key] = None if not val.strip() else _val(val.strip())
        elif cur_key and ln.strip().startswith('- '):
            if root.get(cur_key) is None:
                root[cur_key] = []
            root[cur_key].append(_val(ln.strip()[2:].strip()))
        elif cur_key and ':' in ln:
            if root.get(cur_key) is None:
                root[cur_key] = {}
            key, val = ln.strip().split(':', 1)
            root[cur_key][key.strip()] = _val(val.strip())
    return root


def _val(s: str):
    if s.startswith('['):
        return [x.strip() for x in s.strip('[]').split(',') if x.strip()]
    try:
        return ast.literal_eval(s)
    except Exception:
        try:
            return int(s)
        except ValueError:
            return s
