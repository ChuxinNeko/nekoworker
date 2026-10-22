"""X11 / AT-SPI operations. Runs with the desktop user's session bus and UID."""

import base64
import io
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=8).stdout


def registry():
    import pyatspi

    return pyatspi, pyatspi.Registry.getDesktop(0)


def snapshot_path():
    return Path(os.getenv("XDG_RUNTIME_DIR", "/tmp")) / "nekoworker-tree.json"


def identity(node):
    return [node.getRoleName(), node.name or "", node.getApplication().get_process_id()]


def tree(max_depth=12, max_nodes=500, application="", **_):
    if not 1 <= max_depth <= 30 or not 1 <= max_nodes <= 3000:
        raise ValueError("max_depth must be 1..30 and max_nodes 1..3000")
    atspi, desktop = registry()
    generation = uuid.uuid4().hex[:12]
    handles, nodes, warnings = {}, [], []
    truncated = False

    def walk(node, path, depth, parent):
        nonlocal truncated
        if len(nodes) >= max_nodes:
            truncated = True
            return
        try:
            role, name, pid = identity(node)
            ident = f"{generation}:{len(nodes)}"
            states = node.getState().getStates()
            state_names = [
                getattr(s, "value_nick", str(s).split("STATE_")[-1].split()[0].lower())
                for s in states
            ]
            item = {
                "id": ident,
                "parent": parent,
                "role": role,
                "name": name[:1000],
                "pid": pid,
                "states": state_names,
                "actions": [],
            }
            handles[ident] = {"path": path, "identity": [role, name, pid]}
            try:
                rect = node.queryComponent().getExtents(atspi.DESKTOP_COORDS)
                item["bounds"] = [rect.x, rect.y, rect.width, rect.height]
            except NotImplementedError:
                pass
            try:
                action = node.queryAction()
                item["actions"] = [action.getName(i) for i in range(action.nActions)]
            except NotImplementedError:
                pass
            # Password fields must never appear in model text context.
            if role != "password text":
                try:
                    text = node.queryText()
                    item["text"] = text.getText(0, min(text.characterCount, 2000))
                except NotImplementedError:
                    pass
            nodes.append(item)
            if depth >= max_depth:
                truncated |= node.childCount > 0
                return
            for index in range(min(node.childCount, max_nodes)):
                if len(nodes) >= max_nodes:
                    truncated = True
                    break
                child = node.getChildAtIndex(index)
                if child is not None:
                    walk(child, path + [index], depth + 1, ident)
        except Exception as exc:
            warnings.append(f"Skipped inaccessible node at {path}: {type(exc).__name__}")

    for index in range(desktop.childCount):
        app = desktop.getChildAtIndex(index)
        if app is not None and (not application or application.lower() in app.name.lower()):
            walk(app, [index], 0, None)
    path = snapshot_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(handles))
    temporary.chmod(0o600)
    temporary.replace(path)
    return {
        "generation": generation,
        "nodes": nodes,
        "truncated": truncated,
        "warnings": warnings,
        "hint": "IDs expire on the next tree call. Refresh after UI changes.",
    }


def resolve(element_id):
    path = snapshot_path()
    handles = json.loads(path.read_text()) if path.exists() else {}
    if element_id not in handles:
        raise ValueError("Unknown or expired element ID; call desktop_tree again")
    _, node = registry()
    entry = handles[element_id]
    for index in entry["path"]:
        node = node.getChildAtIndex(index)
        if node is None:
            raise ValueError("Element disappeared; refresh desktop_tree")
    if identity(node) != entry["identity"]:
        raise ValueError("Element changed; refresh desktop_tree")
    return node


def element(element_id, action="click", text="", **_):
    node = resolve(element_id)
    if action == "focus":
        if not node.queryComponent().grabFocus():
            raise ValueError("Element refused focus")
    elif action == "set_text":
        editable = node.queryEditableText()
        accepted = editable.setTextContents(text)
        # Firefox may report success without changing the field. Fall back to a
        # human-style replacement, but only after the app explicitly grants focus.
        current = node.queryText().getText(0, -1)
        if not accepted or current != text:
            if not node.queryComponent().grabFocus():
                raise ValueError("Element refused focus for text replacement")
            run("xdotool", "key", "--clearmodifiers", "ctrl+a")
            type_text(text)
    else:
        interface = node.queryAction()
        names = [interface.getName(i) for i in range(interface.nActions)]
        if action not in names:
            raise ValueError(f"Unsupported action {action!r}; available: {names}")
        if not interface.doAction(names.index(action)):
            raise ValueError("Application refused action")
    return {"ok": True, "refresh_tree": True}


def screenshot(**_):
    import mss
    from PIL import Image

    with mss.mss() as capture:
        shot = capture.grab(capture.monitors[0])
        output = io.BytesIO()
        Image.frombytes("RGB", shot.size, shot.rgb).save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode()


def pointer(x, y, button=1, clicks=1, **_):
    if x < 0 or y < 0 or button not in (1, 2, 3) or not 1 <= clicks <= 3:
        raise ValueError("Invalid coordinates, button (1..3), or clicks (1..3)")
    run(
        "xdotool",
        "mousemove",
        "--sync",
        str(x),
        str(y),
        "click",
        "--repeat",
        str(clicks),
        "--delay",
        "100",
        str(button),
    )
    return {"ok": True}


def drag(x1, y1, x2, y2, **_):
    if min(x1, y1, x2, y2) < 0:
        raise ValueError("Coordinates must be nonnegative")
    try:
        run("xdotool", "mousemove", "--sync", str(x1), str(y1), "mousedown", "1")
        run("xdotool", "mousemove", "--sync", str(x2), str(y2))
    finally:
        run("xdotool", "mouseup", "1")
    return {"ok": True}


def scroll(direction="down", amount=3, **_):
    buttons = {"up": "4", "down": "5", "left": "6", "right": "7"}
    if direction not in buttons or not 1 <= amount <= 50:
        raise ValueError("Invalid direction or amount (1..50)")
    run("xdotool", "click", "--repeat", str(amount), "--delay", "50", buttons[direction])
    return {"ok": True}


def key(keys, **_):
    if not keys or keys.startswith("-") or len(keys) > 200:
        raise ValueError("Invalid X11 key chord")
    run("xdotool", "key", "--clearmodifiers", keys)
    return {"ok": True}


def type_text(text, paste_keys="ctrl+v", **_):
    if paste_keys not in ("ctrl+v", "ctrl+shift+v", "shift+Insert"):
        raise ValueError("paste_keys must be ctrl+v, ctrl+shift+v, or shift+Insert")
    if len(text) > 50000:
        raise ValueError("Text exceeds 50000 characters")
    # xclip forks a selection owner. Do not retain captured stdout pipes.
    subprocess.run(
        ["xclip", "-selection", "clipboard"],
        input=text.encode(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=5,
    )
    run("xdotool", "key", "--clearmodifiers", paste_keys)
    return {"ok": True}


def windows(**_):
    output = run("wmctrl", "-lpG")
    return {"windows": output.splitlines()}


def focus_window(window_id, **_):
    if not window_id.startswith("0x") or not all(
        c in "0123456789abcdefABCDEF" for c in window_id[2:]
    ):
        raise ValueError("Use a hexadecimal window ID from desktop_windows")
    run("wmctrl", "-ia", window_id)
    return {"ok": True}


def launch(argv, **_):
    if not argv or not all(isinstance(arg, str) for arg in argv):
        raise ValueError("argv must be a nonempty list of strings")
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {"pid": proc.pid}


OPERATIONS = {
    f.__name__: f
    for f in (
        tree,
        element,
        screenshot,
        pointer,
        drag,
        scroll,
        key,
        type_text,
        windows,
        focus_window,
        launch,
    )
}


def main():
    try:
        args = json.load(sys.stdin)
        operation = args.pop("operation")
        result = OPERATIONS[operation](**args)
        print(json.dumps({"result": result}))
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))


if __name__ == "__main__":
    main()
