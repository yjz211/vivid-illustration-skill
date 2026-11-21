#!/usr/bin/env python
"""Inject compatibility assets without changing any vendored skill prompt."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from resolve_runtime import resolve


MODELING_MARKERS = (
    "FIGURE_MANIFEST", "数学建模", "数模", "MCM", "ICM",
    "CUMCM", "APMCM", "PROBLEM_ANALYSIS",
)


def detect_profile(workspace: Path) -> str:
    candidates = [
        workspace / "PROBLEM_ANALYSIS.md",
        workspace / "PAPER_PLAN.md",
        workspace / "MODELING_REPORT.md",
        workspace / ".vivid/config.json",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")[:500_000]
        if any(marker.lower() in text.lower() for marker in MODELING_MARKERS):
            return "modeling-competition"
    return "general-paper"


def copy_tree_files(source: Path, destination: Path, force: bool = False):
    copied = 0
    skipped = 0
    destination.mkdir(parents=True, exist_ok=True)
    for src in source.rglob("*"):
        if not src.is_file() or src.suffix in (".enc", ".pyc") or "__pycache__" in src.parts:
            continue
        rel = src.relative_to(source)
        dst = destination / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and not force:
            baselines_path = Path(__file__).with_name('resource-baselines.json')
            baselines = json.loads(baselines_path.read_text(encoding='utf-8')) if baselines_path.exists() else {}
            if sha256(dst) not in baselines.get(src.name, []):
                skipped += 1
                continue
        shutil.copy2(src, dst)
        copied += 1
    return copied, skipped


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--profile", choices=["auto", "general-paper", "modeling-competition"], default="auto")
    parser.add_argument("--capability", default="all")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    if not workspace.is_dir():
        raise SystemExit(f"Workspace does not exist: {workspace}")
    # --workspace explicitly establishes a new project boundary, even inside
    # another configured project. Never inherit or update the parent's config.
    config_dir = workspace / ".vivid"
    config_dir.mkdir(parents=True, exist_ok=True)
    try:
        with (config_dir / "config.json").open("x", encoding="utf-8") as handle:
            handle.write("{}\n")
    except FileExistsError:
        pass
    root = Path(__file__).resolve().parent.parent
    assets = root / "assets"
    # Refresh: refresh only the identified pristine helper, preserving custom files.
    for relative in ("_utils/plot_utils.py", "skills/shared-scripts/plot_utils.py"):
        existing = workspace / relative
        if existing.is_file() and sha256(existing) == "63ad0791b7262e562a28e1500ba8f15005ca66e815f6230df1951197beb89a25":
            shutil.copy2(assets / "shared-scripts/plot_utils.py", existing)
    # 0.1.3: refresh recognized routing files only; preserve all user modifications.
    routing_baseline = {"figure_exemplars.md":"cdf35eb68d35f2ef814cf856f338e0f4466fab89d3b5e2954cef6a3ce549add5","figure_style_guide.md":"3dd47915c22557dbe59d5c3af76332ab81468c78fe4e0b6fdf702155f28268e7","get_recipe.py":"3f715cdfcca7532fd5c3c68e79594ea6bd758e21cb9b0c7ea150b1df8afe4065","writing_rules.md":"b133d5296f4b64ec07c60db4dc03b6110b0ecad6ce55e64b460f9e28e9c697e0"}
    for folder in (workspace / "_utils", workspace / "skills/shared-scripts"):
        for filename, expected in routing_baseline.items():
            existing = folder / filename
            src_file = assets / "shared-scripts" / filename
            if existing.is_file() and src_file.is_file() and sha256(existing) == expected:
                shutil.copy2(src_file, existing)
    # Refresh recognized pre-preservation helpers; keep user edits.
    layout_helper_baselines = ["f8bd00832d65a4982f12510a2f097dbabd03b851102a7c6db6fbb3a3d8c2af4f","4fe20ca0f1439a218e5c5ccdb959f8bc295b9e45e107673562b3e3779afcff49","9f47314d5045aad5dfa0863d836b86124aacf5cb90e93cc3c808324bf469aad7"]
    for folder in (workspace / "_utils", workspace / "skills/shared-scripts"):
        existing = folder / "plot_utils.py"
        if existing.is_file() and sha256(existing) in layout_helper_baselines:
            shutil.copy2(assets / "shared-scripts/plot_utils.py", existing)
    profile = detect_profile(workspace) if args.profile == "auto" else args.profile

    utils = workspace / "_utils"
    templates = workspace / "_templates"

    copied_utils, skipped_utils = copy_tree_files(
        assets / "shared-scripts", utils, args.force
    )
    if args.capability in ("all", "html", "paper-figure-html"):
        copied_templates, skipped_templates = copy_tree_files(
            assets / "html-templates", templates, args.force
        )
    else:
        copied_templates, skipped_templates = 0, 0

    runtime = resolve()
    metadata = {
        "schema": 1,
        "profile": profile,
        "capability": args.capability,
        "workspace": str(workspace),
        "runtime_skill": str(root),
        "paths": {
            **runtime,
            "shared_scripts": str(utils),
            "utils": str(utils),
            "templates": str(templates),
        },
        "injection": {
            "utils": {"copied": copied_utils, "preserved": skipped_utils},
            "templates": {"copied": copied_templates, "preserved": skipped_templates},
        },
        "prompt_policy": "drawing semantics and recipe layers are preserved",
    }
    import sys
    sys.path.insert(0, str(assets / 'shared-scripts'))
    from vivid_config import write_config
    write_config(workspace)
    meta_path = workspace / ".vivid/runtime.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

