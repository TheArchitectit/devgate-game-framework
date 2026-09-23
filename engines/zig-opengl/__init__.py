"""devgate-game-framework — Zig + OpenGL engine support.

This module adds quality gates for Zig + OpenGL game projects.
Contributed upstream to TheArchitectit/devgate-game-framework.

Modules:
- scanner.py: Discover .zig files, extract entity/handler definitions
- manifest.py: Read game-manifest.json for engine detection
- patterns.json: Zig-specific regression patterns (Z001-Z010)

Usage:
    from engines.zig_opengl.scanner import scan_project
    from engines.zig_opengl.manifest import load_manifest

Example:
    results = scan_project(Path("/path/to/project"))
    print(results["passed"])
"""

__version__ = "1.0.0"
__engine__ = "Zig + OpenGL"
