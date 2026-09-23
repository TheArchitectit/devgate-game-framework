#!/usr/bin/env python3
"""Game-class regression scanner (engine-aware).

Detects project engine from game-manifest.json and uses engine-specific patterns.
Falls back to Godot patterns for unknown engines.

Reads .guardrails/failure-registry.jsonl and scans staged/unstaged changes.
Exit 1 on hard violations with --pre-commit.
"""
import json, os, re, sys, subprocess
from pathlib import Path

# Engine-specific pattern tables
GODOT_PATTERNS = {
    "NULL_DEREF": [
        r"\.get_node\([^)]*\)\s*\.\s*\w+",
        r"if\s+\w+\s*==\s*null\s*:\s*pass",
    ],
    "SCENE_LOAD_FAIL": [
        r"load\([^)]*\.tscn[^)]*\)\s*$",
        r"change_scene_to_file\([^)]*\)",
    ],
    "SAVE_CORRUPT": [
        r"json\.parse\([^)]*\)\s*$",
        r"FileAccess\.open[^)]*\)\s*$",
    ],
    "SCRIPT_ERROR": [
        r"push_error\(",
        r"assert\(",
    ],
    "ORPHAN_SIGNAL": [
        r'\.connect\("pressed"',
    ],
}

ZIG_PATTERNS = {
    "ZIG_COMPILE": [
        r"error:.*unexpected",
        r"compile error",
    ],
    "ZIG_MEMORY": [
        r"std\.mem\.alloc\(",
    ],
    "OPENGL_CTX": [
        r"glGetError\(\)",
    ],
    "SHADER_FAIL": [
        r"glCompileShader",
    ],
    "INPUT_CAPTURE": [
        r"glfwSetKeyCallback",
    ],
}

ENGINE_PATTERNS = {
    "Godot": GODOT_PATTERNS,
    "Zig + OpenGL": ZIG_PATTERNS,
}

# Registry ID prefixes per engine
ENGINE_REGISTRY_PREFIXES = {
    "Godot": {"F001", "F002", "F003", "F004", "F005", "F006", "F007"},
    "Zig + OpenGL": {"Z001", "Z002", "Z003", "Z004", "Z005", "Z006", "Z007", "Z008", "Z009", "Z010", "F008", "F009", "F010", "F011", "F012", "F013"},
}

# Directories to exclude from scanning
EXCLUDE_DIRS = {"external", "scripts", ".git", "node_modules", "build", "assets", "openclaw", "devgate-upstream-contrib", "engines"}

# File extensions to scan
SCAN_EXTENSIONS = {".gd", ".tscn", ".zig", ".ts", ".js", ".py", ".rs", ".go"}


def find_project_root():
    d = Path.cwd()
    for i in range(20):
        for marker in ("project.godot", "build.zig", "game-manifest.json", ".git"):
            if (d / marker).exists():
                return d
        parent = d.parent
        if parent == d:
            break
        d = parent
    return Path.cwd()


def detect_engine(root):
    manifest_path = root / "game-manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            return manifest.get("engine", "unknown")
        except:
            pass
    if (root / "project.godot").exists():
        return "Godot"
    if (root / "build.zig").exists():
        return "Zig + OpenGL"
    return "unknown"


def should_scan_file(file_path, root):
    try:
        rel = file_path.relative_to(root)
    except ValueError:
        return False
    for part in rel.parts[:-1]:
        if part in EXCLUDE_DIRS:
            return False
    if file_path.suffix not in SCAN_EXTENSIONS:
        return False
    return True


def load_failure_registry(root, engine=None):
    registry_path = root / ".guardrails" / "failure-registry.jsonl"
    entries = []
    if not registry_path.exists():
        return entries
    allowed = ENGINE_REGISTRY_PREFIXES.get(engine, None)
    for line in registry_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            entry = json.loads(line)
            if allowed is not None:
                fid = entry.get("failure_id", "")
                if not any(fid.startswith(p) for p in allowed):
                    continue
            entries.append(entry)
        except json.JSONDecodeError:
            continue
    return entries


def get_changed_files(root, staged=True):
    cmd = ["git", "diff", "--name-only", "--cached"] if staged else ["git", "diff", "--name-only"]
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def scan_file_for_patterns(file_path, patterns):
    issues = []
    try:
        content = Path(file_path).read_text(errors="replace")
    except Exception:
        return issues
    for line_num, line in enumerate(content.splitlines(), 1):
        if "guardrails-allow" in line:
            continue
        for pname, regexes in patterns.items():
            for regex in regexes:
                try:
                    if re.search(regex, line):
                        issues.append({"file": str(file_path), "line": line_num, "pattern": pname, "match": line.strip()[:120]})
                except re.error:
                    continue
    return issues


def scan_failure_registry_patterns(file_path, entries):
    issues = []
    try:
        content = Path(file_path).read_text(errors="replace")
    except Exception:
        return issues
    for entry in entries:
        pattern = entry.get("regression_pattern")
        if not pattern:
            continue
        try:
            for line_num, line in enumerate(content.splitlines(), 1):
                if "guardrails-allow" in line:
                    continue
                if re.search(pattern, line):
                    issues.append({"file": str(file_path), "line": line_num, "pattern": f"REGISTRY:{entry.get('failure_id', 'unknown')}", "match": line.strip()[:120]})
        except re.error:
            continue
    return issues


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Game-class regression scanner (engine-aware)")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--unstaged", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--pre-commit", action="store_true")
    args = parser.parse_args()

    root = find_project_root()
    engine = detect_engine(root)
    print(f"[game-regression] project root: {root}")
    print(f"[game-regression] detected engine: {engine}")

    registry = load_failure_registry(root, engine)
    print(f"[game-regression] failure registry: {len(registry)} entries")

    active_patterns = ENGINE_PATTERNS.get(engine, GODOT_PATTERNS)

    if args.all:
        files = [p for ext in SCAN_EXTENSIONS for p in root.rglob(f"*{ext}") if should_scan_file(p, root)]
    elif args.staged or args.unstaged:
        files = [root / f for f in get_changed_files(root, staged=args.staged) if should_scan_file(root / f, root)]
    else:
        files = [p for ext in SCAN_EXTENSIONS for p in root.rglob(f"*{ext}") if should_scan_file(p, root)]

    if not files:
        print("[game-regression] no files to scan")
        sys.exit(0)

    print(f"[game-regression] scanning {len(files)} file(s)")
    all_issues = []
    for f in files:
        issues = scan_file_for_patterns(str(f), active_patterns)
        issues.extend(scan_failure_registry_patterns(str(f), registry))
        all_issues.extend(issues)

    if all_issues:
        print(f"\n[game-regression] {len(all_issues)} issue(s) found:")
        for issue in all_issues:
            print(f"  {issue['pattern']}: {issue['file']}:{issue['line']} — {issue['match']}")
    else:
        print("[game-regression] no issues found")

    print(f"\n=== Game Regression Summary ===")
    print(f"Files scanned: {len(files)}, Issues: {len(all_issues)}")
    if args.pre_commit and all_issues:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
