#!/usr/bin/env python3
"""Scene inventory + button handler validation scanner.

Engine-aware: detects project engine from game-manifest.json and dispatches
to the appropriate scanner (Godot, Zig+OpenGL, etc.).

For Godot projects: discovers .tscn files, parses Button nodes and signal connections.
For Zig+OpenGL projects: discovers .zig files under src/ui/, validates handler bindings.

Exit codes: 0 = all scenes pass, 1 = any scene/button failure.
"""
import json, os, re, sys
from pathlib import Path


def find_project_root():
    d = Path.cwd()
    for i in range(20):
        for marker in ("project.godot", "build.zig", "game-manifest.json", "package.json", "Cargo.toml", ".git"):
            if (d / marker).exists():
                return d
        parent = d.parent
        if parent == d:
            break
        d = parent
    return Path.cwd()


def detect_engine(root):
    """Detect engine from game-manifest.json or project files."""
    manifest_path = root / "game-manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            return manifest.get("engine", "unknown")
        except:
            pass
    # Fallback: detect by project files
    if (root / "project.godot").exists():
        return "Godot"
    if (root / "build.zig").exists():
        return "Zig + OpenGL"
    return "unknown"


# === GODOT SCANNER ===

def discover_scenes_godot(root):
    """Find all .tscn files under src/."""
    scenes = []
    src = root / "src"
    if not src.is_dir():
        return scenes
    for p in sorted(src.rglob("*.tscn")):
        scenes.append(str(p.relative_to(root)))
    return scenes


def parse_tscn_buttons(scene_path):
    """Parse a .tscn file for Button nodes and signal connections."""
    import xml.etree.ElementTree as ET
    text = Path(scene_path).read_text(errors="replace")

    buttons = []
    for m in re.finditer(r'\[node\s+name="([^"]+)"[^]]*type="Button"', text):
        buttons.append(m.group(1))

    connections = []
    for m in re.finditer(
        r'\[connection\s+signal="([^"]+)"\s+from="([^"]+)"\s+to="([^"]+)"\s+method="([^"]+)"',
        text,
    ):
        connections.append({
            "signal": m.group(1),
            "from": m.group(2),
            "to": m.group(3),
            "method": m.group(4),
        })

    connected = {c["from"] for c in connections if c["signal"] == "pressed"}
    orphaned = [b for b in buttons if b not in connected]
    return buttons, connections, orphaned


def scan_godot(root):
    scenes = discover_scenes_godot(root)
    if not scenes:
        print("[scene-inventory] no .tscn scenes found — nothing to scan")
        return 0

    print(f"[scene-inventory] discovered {len(scenes)} Godot scene(s)")
    failures = 0
    orphan_count = 0

    for scene in scenes:
        full = root / scene
        try:
            buttons, connections, orphaned = parse_tscn_buttons(str(full))
        except Exception as e:
            print(f"  FAIL {scene}: parse error — {e}")
            failures += 1
            continue

        status = "OK"
        if orphaned:
            status = f"ORPHANED: {len(orphaned)} button(s) without 'pressed' handler"
            orphan_count += len(orphaned)
            failures += 1

        print(f"  {'FAIL' if orphaned else 'OK'} {scene} — {len(buttons)} button(s), {len(connections)} connection(s){' — ' + status if orphans else ''}")
        for o in orphaned:
            print(f"    ORPHAN: Button '{o}' has no 'pressed' signal connection")

    print(f"\n=== Scene Inventory Summary ===")
    print(f"Scenes: {len(scenes)}, Failures: {failures}, Orphaned buttons: {orphan_count}")
    return 1 if failures > 0 else 0


# === ZIG+OPENGL SCANNER ===

def discover_zig_screens(root):
    """Find .zig files under src/ui/ — Zig project UI screens."""
    screens = []
    ui_dir = root / "src" / "ui"
    if not ui_dir.is_dir():
        return screens
    for p in sorted(ui_dir.rglob("*.zig")):
        screens.append(str(p.relative_to(root)))
    return screens


def parse_zig_handlers(screen_path):
    """Parse a .zig file for UI handler functions and entity definitions."""
    text = Path(screen_path).read_text(errors="replace")

    buttons = []
    for m in re.finditer(r'\.label\s*=\s*"([^"]+)"', text):
        label = m.group(1)
        label_pos = m.start()
        nearby = text[label_pos:label_pos + 500]
        handler_match = re.search(r'\.handler\s*=\s*"([^"]+)"', nearby)
        if handler_match:
            buttons.append({"label": label, "handler": handler_match.group(1)})

    internal_fns = {
        "init", "update", "render", "handle_input", "deinit",
        "show", "hide", "updateHUD", "checkWarnings", "showAnimation",
        "initScreen", "showScreen", "hideScreen",
    }
    handlers = []
    for m in re.finditer(r'(?:pub\s+)?fn\s+(\w+)\s*\(', text):
        fn = m.group(1)
        if fn not in internal_fns:
            handlers.append(fn)

    button_handlers = {b["handler"] for b in buttons}
    orphans = [h for h in handlers if h not in button_handlers]
    return buttons, handlers, orphans


def scan_zig(root):
    screens = discover_zig_screens(root)
    if not screens:
        print("[scene-inventory] no Zig UI screens found under src/ui/")
        return 0

    print(f"[scene-inventory] discovered {len(screens)} Zig screen(s) under src/ui/")
    failures = 0
    orphan_count = 0

    for screen in screens:
        full = root / screen
        buttons, handlers, orphans = parse_zig_handlers(str(full))

        if not buttons and not handlers:
            print(f"  SKIP {screen} — no UI definitions found")
            continue

        status = "OK"
        if orphans:
            status = f"ORPHANED: {len(orphans)} handler(s) without button connection"
            orphan_count += len(orphans)
            failures += 1

        print(f"  {'FAIL' if orphans else 'OK'} {screen} — {len(buttons)} button(s), {len(handlers)} handler(s){' — ' + status if orphans else ''}")
        for o in orphans:
            print(f"    ORPHAN: Handler '{o}' has no connected button/entity")

    print(f"\n=== Scene Inventory Summary ===")
    print(f"Screens: {len(screens)}, Failures: {failures}, Orphaned handlers: {orphan_count}")
    return 1 if failures > 0 else 0


# === MAIN DISPATCH ===

def scan_project(root):
    root = Path(root)
    engine = detect_engine(root)
    print(f"[scene-inventory] detected engine: {engine}")

    if engine == "Zig + OpenGL":
        return scan_zig(root)
    elif engine == "Godot":
        return scan_godot(root)
    else:
        # Try Godot first, then Zig
        if (root / "project.godot").exists():
            return scan_godot(root)
        if (root / "build.zig").exists():
            return scan_zig(root)
        print(f"[scene-inventory] unknown engine — no scenes to scan")
        return 0


if __name__ == "__main__":
    root = find_project_root()
    print(f"[scene-inventory] project root: {root}")
    sys.exit(scan_project(root))
