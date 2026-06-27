import contextlib
import io
import json
import os
import queue
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import unreal


HOST = os.environ.get("PROPHECY_EDITOR_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("PROPHECY_EDITOR_BRIDGE_PORT", "8765"))
MAX_PORT_TRIES = int(os.environ.get("PROPHECY_EDITOR_BRIDGE_PORT_TRIES", "20"))

_REQUESTS = queue.Queue()
_SERVER = None
_THREAD = None
_TICK_HANDLE = None
_EXEC_GLOBALS = {"unreal": unreal}


def _json_default(value):
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        return [float(value.x), float(value.y), float(value.z)]
    if hasattr(value, "r") and hasattr(value, "g") and hasattr(value, "b"):
        return [float(value.r), float(value.g), float(value.b), float(getattr(value, "a", 1.0))]
    return str(value)


def _send_json(handler, status, payload):
    body = json.dumps(payload, indent=2, sort_keys=True, default=_json_default).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
    handler.end_headers()
    handler.wfile.write(body)


def _ok(payload=None):
    result = {"ok": True}
    if payload:
        result.update(payload)
    return result


def _error(message, details=None):
    result = {"ok": False, "error": str(message)}
    if details:
        result["details"] = str(details)
    return result


def _queue_editor_call(fn, timeout=30.0):
    item = {
        "fn": fn,
        "event": threading.Event(),
        "result": None,
    }
    _REQUESTS.put(item)
    if not item["event"].wait(timeout):
        return _error("Timed out waiting for the Unreal editor thread.")
    return item["result"]


def _class_name(obj):
    try:
        return obj.get_class().get_name()
    except Exception:
        return type(obj).__name__


def _path_name(obj):
    if obj is None:
        return None
    try:
        return obj.get_path_name()
    except Exception:
        return str(obj)


def _actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        try:
            return actor.get_name()
        except Exception:
            return str(actor)


def _vector3(value):
    if value is None:
        return [0.0, 0.0, 0.0]
    return [
        float(getattr(value, "x", 0.0)),
        float(getattr(value, "y", 0.0)),
        float(getattr(value, "z", 0.0)),
    ]


def _safe_property(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def _get_editor_world():
    try:
        subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if subsystem:
            world = subsystem.get_editor_world()
            if world:
                return world
    except Exception:
        pass

    try:
        return unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        return None


def _get_all_level_actors():
    try:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem:
            return list(subsystem.get_all_level_actors())
    except Exception:
        pass

    try:
        return list(unreal.EditorLevelLibrary.get_all_level_actors())
    except Exception:
        return []


def _component_location(component, actor):
    try:
        return _vector3(component.get_component_location())
    except Exception:
        try:
            return _vector3(actor.get_actor_location())
        except Exception:
            return [0.0, 0.0, 0.0]


def _component_scale(component):
    try:
        return _vector3(component.get_component_scale())
    except Exception:
        return [1.0, 1.0, 1.0]


def _component_decal_size(component):
    value = _safe_property(component, "decal_size", None)
    if value is not None:
        return _vector3(value)
    return None


def _component_material(component):
    mat = _safe_property(component, "decal_material", None)
    if mat is None:
        try:
            mat = component.get_material(0)
        except Exception:
            mat = None
    return _path_name(mat)


def _component_visible(component):
    visible = True
    for prop in ("visible", "hidden_in_game"):
        value = _safe_property(component, prop, None)
        if prop == "visible" and value is not None:
            visible = visible and bool(value)
        if prop == "hidden_in_game" and value is not None:
            visible = visible and not bool(value)
    try:
        visible = visible and bool(component.is_visible())
    except Exception:
        pass
    return visible


def _round_bucket(location, bucket_cm):
    return (
        int(round(location[0] / bucket_cm)),
        int(round(location[1] / bucket_cm)),
        int(round(location[2] / bucket_cm)),
    )


def _summarize_cluster(key, cluster):
    count = max(cluster["count"], 1)
    center = [
        cluster["sum_location"][0] / count,
        cluster["sum_location"][1] / count,
        cluster["sum_location"][2] / count,
    ]
    materials = sorted(cluster["materials"].items(), key=lambda item: item[1], reverse=True)
    owner_classes = sorted(cluster["owner_classes"].items(), key=lambda item: item[1], reverse=True)
    return {
        "bucket": key,
        "count": cluster["count"],
        "visible_count": cluster["visible_count"],
        "center_cm": center,
        "sample_owners": cluster["sample_owners"],
        "top_materials": [{"material": name, "count": count} for name, count in materials[:8]],
        "top_owner_classes": [{"class": name, "count": count} for name, count in owner_classes[:8]],
        "avg_decal_size_cm": [
            cluster["sum_decal_size"][0] / max(cluster["decal_size_count"], 1),
            cluster["sum_decal_size"][1] / max(cluster["decal_size_count"], 1),
            cluster["sum_decal_size"][2] / max(cluster["decal_size_count"], 1),
        ] if cluster["decal_size_count"] else None,
    }


def _build_decal_report(bucket_cm=5.0, limit=25):
    bucket_cm = max(float(bucket_cm), 0.1)
    limit = max(int(limit), 1)
    actors = _get_all_level_actors()
    world = _get_editor_world()

    decal_actor_count = 0
    decal_component_count = 0
    visible_decal_component_count = 0
    owner_class_counts = {}
    material_counts = {}
    clusters = {}
    actor_class_counts = {}
    entries = []

    for actor in actors:
        actor_class = _class_name(actor)
        actor_class_counts[actor_class] = actor_class_counts.get(actor_class, 0) + 1
        if "Decal" in actor_class:
            decal_actor_count += 1

        try:
            components = list(actor.get_components_by_class(unreal.DecalComponent))
        except Exception:
            components = []

        for component in components:
            decal_component_count += 1
            visible = _component_visible(component)
            if visible:
                visible_decal_component_count += 1

            location = _component_location(component, actor)
            bucket = _round_bucket(location, bucket_cm)
            bucket_key = "{},{},{}".format(bucket[0], bucket[1], bucket[2])
            material = _component_material(component) or "<none>"
            decal_size = _component_decal_size(component)
            owner_label = _actor_label(actor)
            owner_class_counts[actor_class] = owner_class_counts.get(actor_class, 0) + 1
            material_counts[material] = material_counts.get(material, 0) + 1

            cluster = clusters.setdefault(bucket_key, {
                "count": 0,
                "visible_count": 0,
                "sum_location": [0.0, 0.0, 0.0],
                "sum_decal_size": [0.0, 0.0, 0.0],
                "decal_size_count": 0,
                "materials": {},
                "owner_classes": {},
                "sample_owners": [],
            })
            cluster["count"] += 1
            cluster["visible_count"] += 1 if visible else 0
            cluster["sum_location"][0] += location[0]
            cluster["sum_location"][1] += location[1]
            cluster["sum_location"][2] += location[2]
            cluster["materials"][material] = cluster["materials"].get(material, 0) + 1
            cluster["owner_classes"][actor_class] = cluster["owner_classes"].get(actor_class, 0) + 1
            if len(cluster["sample_owners"]) < 8:
                cluster["sample_owners"].append(owner_label)
            if decal_size is not None:
                cluster["decal_size_count"] += 1
                cluster["sum_decal_size"][0] += decal_size[0]
                cluster["sum_decal_size"][1] += decal_size[1]
                cluster["sum_decal_size"][2] += decal_size[2]

            if len(entries) < limit:
                entries.append({
                    "owner": owner_label,
                    "owner_class": actor_class,
                    "component": _path_name(component),
                    "location_cm": location,
                    "scale": _component_scale(component),
                    "decal_size_cm": decal_size,
                    "visible": visible,
                    "material": material,
                    "sort_order": _safe_property(component, "sort_order", None),
                    "fade_screen_size": _safe_property(component, "fade_screen_size", None),
                })

    top_clusters = [
        _summarize_cluster(key, cluster)
        for key, cluster in sorted(clusters.items(), key=lambda item: item[1]["count"], reverse=True)[:limit]
    ]

    warnings = []
    if decal_component_count >= 500:
        warnings.append("High decal component count. Deferred decals can become expensive even when overlapping visually collapse into one stain.")
    if top_clusters and top_clusters[0]["count"] >= 50:
        warnings.append("Large same-location decal cluster detected. This is the classic 2000-overlapping-decals-at-one-point performance trap.")
    if visible_decal_component_count != decal_component_count:
        warnings.append("Some decal components are hidden, but they may still exist as scene/components depending on how they were disabled.")

    return _ok({
        "bridge_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "map": _path_name(world),
        "actor_count": len(actors),
        "decal_actor_count": decal_actor_count,
        "decal_component_count": decal_component_count,
        "visible_decal_component_count": visible_decal_component_count,
        "bucket_cm": bucket_cm,
        "warnings": warnings,
        "top_location_clusters": top_clusters,
        "top_materials": [
            {"material": name, "count": count}
            for name, count in sorted(material_counts.items(), key=lambda item: item[1], reverse=True)[:limit]
        ],
        "top_decal_owner_classes": [
            {"class": name, "count": count}
            for name, count in sorted(owner_class_counts.items(), key=lambda item: item[1], reverse=True)[:limit]
        ],
        "sample_decals": entries,
        "actor_class_counts_containing_decal": [
            {"class": name, "count": count}
            for name, count in sorted(actor_class_counts.items(), key=lambda item: item[1], reverse=True)
            if "Decal" in name
        ],
    })


def _build_scene_snapshot(limit=50):
    actors = _get_all_level_actors()
    counts = {}
    for actor in actors:
        name = _class_name(actor)
        counts[name] = counts.get(name, 0) + 1
    return _ok({
        "actor_count": len(actors),
        "top_actor_classes": [
            {"class": name, "count": count}
            for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:max(int(limit), 1)]
        ],
    })


def _execute_console(command):
    if not command:
        return _error("Missing console command.")
    world = _get_editor_world()
    if world is None:
        return _error("No editor world found.")
    unreal.SystemLibrary.execute_console_command(world, command)
    return _ok({"command": command})


def _run_python(code):
    if not code:
        return _error("Missing Python code.")
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exec(code, _EXEC_GLOBALS, _EXEC_GLOBALS)
    return _ok({"stdout": stdout.getvalue(), "stderr": stderr.getvalue()})


def _process_editor_queue(_delta_seconds):
    start = time.time()
    while time.time() - start < 0.025:
        try:
            item = _REQUESTS.get_nowait()
        except queue.Empty:
            break
        try:
            item["result"] = item["fn"]()
        except Exception as exc:
            item["result"] = _error(exc, traceback.format_exc())
        finally:
            item["event"].set()


class _BridgeHandler(BaseHTTPRequestHandler):
    server_version = "ProphecyEditorBridge/1.0"

    def log_message(self, fmt, *args):
        unreal.log("[ProphecyEditorBridge] " + (fmt % args))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/health":
            return _send_json(self, 200, _ok({
                "host": HOST,
                "port": self.server.server_address[1],
                "queued_editor_calls": _REQUESTS.qsize(),
            }))

        if parsed.path == "/decal_report":
            bucket_cm = float(query.get("bucket_cm", ["5.0"])[0])
            limit = int(query.get("limit", ["25"])[0])
            result = _queue_editor_call(lambda: _build_decal_report(bucket_cm=bucket_cm, limit=limit))
            return _send_json(self, 200 if result.get("ok") else 500, result)

        if parsed.path == "/scene_snapshot":
            limit = int(query.get("limit", ["50"])[0])
            result = _queue_editor_call(lambda: _build_scene_snapshot(limit=limit))
            return _send_json(self, 200 if result.get("ok") else 500, result)

        if parsed.path == "/console":
            command = query.get("cmd", [""])[0]
            result = _queue_editor_call(lambda: _execute_console(command))
            return _send_json(self, 200 if result.get("ok") else 500, result)

        if parsed.path == "/shutdown":
            result = _ok({"message": "Bridge shutdown requested."})
            _send_json(self, 200, result)
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        _send_json(self, 404, _error("Unknown endpoint: {}".format(parsed.path)))

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if parsed.path == "/python":
            code = payload.get("code", "")
            result = _queue_editor_call(lambda: _run_python(code), timeout=float(payload.get("timeout", 30.0)))
            return _send_json(self, 200 if result.get("ok") else 500, result)

        if parsed.path == "/console":
            command = payload.get("cmd", "")
            result = _queue_editor_call(lambda: _execute_console(command))
            return _send_json(self, 200 if result.get("ok") else 500, result)

        _send_json(self, 404, _error("Unknown endpoint: {}".format(parsed.path)))


def start_bridge():
    global _SERVER, _THREAD, _TICK_HANDLE
    if _SERVER is not None:
        return

    last_error = None
    for port in range(PORT, PORT + MAX_PORT_TRIES):
        try:
            _SERVER = ThreadingHTTPServer((HOST, port), _BridgeHandler)
            break
        except OSError as exc:
            last_error = exc
    if _SERVER is None:
        raise RuntimeError("Could not bind Prophecy editor bridge: {}".format(last_error))

    _THREAD = threading.Thread(target=_SERVER.serve_forever, name="ProphecyEditorBridge", daemon=True)
    _THREAD.start()
    _TICK_HANDLE = unreal.register_slate_post_tick_callback(_process_editor_queue)
    _EXEC_GLOBALS["bridge_decal_report"] = _build_decal_report
    _EXEC_GLOBALS["bridge_scene_snapshot"] = _build_scene_snapshot
    unreal.log("[ProphecyEditorBridge] Listening on http://{}:{}".format(HOST, _SERVER.server_address[1]))


start_bridge()
