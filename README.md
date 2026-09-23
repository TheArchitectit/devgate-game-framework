# devgate-game-framework

Game-development quality gates for AI-assisted game builds, pulled into DevGate-Agentic-Framework as a git submodule.

## Engines

| Engine | Status | Reference |
|---|---|---|
| **Godot** | ✅ Stable | Sword of Hope |
| **Zig + OpenGL** | 🆕 Proposed | Zombie Diver |

## Modules

- **Game-Type Phase Matrix** — minimum required features/screens/verification per game type × phase (Prototype→Alpha→Beta→Release→Post-release)
- **Per-Screen Feature Tracking + Button Validation** — scene inventory, node/button registry, scene-load smoke, orphaned-signal detection
- **Game Regression Tracking** — failure-registry + regression scanner scaled to gameplay/crash/save-corruption patterns

## Engine-Aware Scanning

The framework auto-detects your project engine from `game-manifest.json` and uses the appropriate scanner:

```bash
# Auto-detect engine and scan
python scripts/scene_inventory.py --all
python scripts/game_regression.py --all

# Pre-commit mode
python scripts/scene_inventory.py --staged --pre-commit
python scripts/game_regression.py --staged --pre-commit
```

### Godot Projects
- Detects: `project.godot` or `game-manifest.json` with `"engine": "Godot"`
- Scene inventory: scans `.tscn` files under `src/` for Button nodes and signal connections
- Regression: Godot-specific patterns (NULL_DEREF, SCENE_LOAD_FAIL, SCRIPT_ERROR, etc.)

### Zig + OpenGL Projects
- Detects: `build.zig` or `game-manifest.json` with `"engine": "Zig + OpenGL"`
- Scene inventory: scans `.zig` files under `src/ui/` for handler functions and button bindings
- Regression: Zig-specific patterns (ZIG_COMPILE, ZIG_MEMORY, OPENGL_CTX, etc.)

## Directory Structure

```
devgate-game-framework/
├── engines/
│   ├── godot/                    # Godot engine support
│   └── zig-opengl/               # Zig + OpenGL engine support
│       ├── __init__.py
│       ├── scanner.py
│       ├── manifest.py
│       └── patterns.json
├── scripts/
│   ├── scene_inventory.py        # Engine-aware dispatcher
│   └── game_regression.py        # Engine-aware dispatcher
├── openspec/specs/
│   ├── zig-opengl-engine/        # Zig engine spec
│   ├── game-type-phase-matrix/
│   ├── per-screen-tracking/
│   └── game-regression/
└── README.md
```

## Attach

```bash
git submodule add git@github.com:TheArchitectit/devgate-game-framework.git game-framework
```

## Reference Implementations

- **Sword of Hope** — Godot reference (`scene_load_check.gd`, `automated_gameplay_test.gd`, `integration_runner.gd`, `.guardrails/failure-registry.jsonl`, `regression_check.py`)
- **Zombie Diver** — Zig + OpenGL reference (first Zig+OpenGL project using this framework)
