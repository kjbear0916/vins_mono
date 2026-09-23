# Copyright 2026. Config loading for disaster_drone_ws.
"""Load scene YAML files. Prefers PyYAML (container); falls back to a minimal
parser for the subset emitted by ``scene_gen/make_scene.py`` so the config can
be consumed and unit-tested without any third-party dependency."""

import os


def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1].replace("''", "'").replace('""', '"')
    return s


def _scalar(v):
    v = v.strip()
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return _unquote(v)
    try:
        if "." in v or "e" in low:
            return float(v)
        return int(v)
    except ValueError:
        return _unquote(v)


def parse_tree(text):
    entries = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entries.append((len(line) - len(line.lstrip()), stripped))

    def parse(idx, indent):
        node = {}
        list_mode = False
        while idx < len(entries):
            ind, content = entries[idx]
            if ind < indent:
                break
            if ind > indent:
                raise ValueError(f"unexpected indent {ind} (expected {indent}): {content!r}")
            if content.startswith("-"):
                if not list_mode:
                    if node:
                        raise ValueError("map before list item at same indent")
                    node = []
                    list_mode = True
                rest = content[1:].strip()
                if rest:
                    node.append(_scalar(rest))
                    idx += 1
                else:
                    idx += 1
                    child, idx = parse(idx, indent + 2)
                    node.append(child)
            else:
                if list_mode:
                    raise ValueError("mapping key inside list block")
                key, sep, value = content.partition(":")
                if not sep:
                    raise ValueError(f"expected ':' in {content!r}")
                key = _unquote(key.strip())
                value = value.strip()
                idx += 1
                if value:
                    node[key] = _scalar(value)
                else:
                    child, idx = parse(idx, indent + 2)
                    node[key] = child
        return node, idx

    root, idx = parse(0, 0)
    if idx != len(entries):
        raise ValueError("trailing content not consumed")
    return root


def load_yaml_file(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        return parse_tree(text)


class Config:
    """Typed accessors over the three scene config files."""

    def __init__(self, package_dir=None):
        self._dir = package_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._cfg_dir = os.path.join(self._dir, "config")
        self._markers = None
        self._zones = None
        self._routes = None

    def marker_map(self):
        if self._markers is None:
            self._markers = load_yaml_file(os.path.join(self._cfg_dir, "marker_map.yaml"))
        return self._markers

    def markers(self):
        raw = self.marker_map().get("markers", {})
        return {int(k): dict(v) for k, v in raw.items()}

    def zones(self):
        if self._zones is None:
            data = load_yaml_file(os.path.join(self._cfg_dir, "occlusion_zones.yaml"))
            self._zones = data.get("zones", [])
        return self._zones

    def routes(self):
        if self._routes is None:
            self._routes = load_yaml_file(os.path.join(self._cfg_dir, "waypoint_routes.yaml"))
        return self._routes

    def marker_pose(self, mid):
        try:
            return self.markers()[int(mid)]
        except (KeyError, ValueError):
            return None

    def zone_for_waypoint(self, mid):
        matches = [z for z in self.zones() if int(z.get("trigger_waypoint", -1)) == int(mid)]
        return matches

    def zones_by_id(self):
        return {str(z.get("id")): z for z in self.zones()}


def marker_floor(mid):
    return int(mid) // 100


def marker_yaw(midpose):
    return float(midpose.get("yaw", 0.0))