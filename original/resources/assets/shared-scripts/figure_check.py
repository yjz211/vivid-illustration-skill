#!/usr/bin/env python3
"""Cross-platform static quality & provenance checker for Vivid data figure scripts.

Usage:
    python _utils/figure_check.py [--workspace .] [--json]
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_grayscale_hex(hex_color: str) -> bool:
    s = hex_color.lstrip("#").lower()
    if len(s) in (3, 4):
        return s[0] == s[1] == s[2]
    if len(s) in (6, 8):
        return s[0:2] == s[2:4] == s[4:6]
    return False


_HEX_COLOR_RE = re.compile(r"\bcolor\s*=\s*['\"](#[0-9a-fA-F]{3,8})['\"]")
_HEX_SKIP_RE = re.compile(r"PALETTE|COLORS\[|edgecolor.*white|facecolor.*white|cmap|linecolor")
_BRIGHT_NAMED_RE = re.compile(r"\bcolor\s*=\s*['\"](?:red|blue|green|orange|purple|brown)['\"]")
_NEUTRAL_NAMED_RE = re.compile(r"\bcolor\s*=\s*['\"](?:grey|gray|black)['\"]")
_RDBU_RE = re.compile(r"cmap\s*=\s*['\"]RdBu(?:_r)?['\"]|cmap.*['\"]RdBu_r['\"]")
_DARK_THEME_RE = re.compile(r"dark_background|darkgrid|set_style\s*\([^)]*dark")
_PDF_LEAK_RE = re.compile(
    r"setup_style.*\.pdf|sys\.path.*\.pdf|palette\s*=.*\.pdf|"
    r"xlabel.*\.pdf|ylabel.*\.pdf|copy2.*\.pdf'"
)
_LEGACY_TONE_RE = re.compile(
    r"#374E55|#00468B|#3B4992|#80796B|#1B1919|#631879|#AD002A|"
    r"#2c3e50|#34495e",
    re.IGNORECASE,
)
_REMOVED_PALETTE_RE = re.compile(r"palette\s*=\s*['\"](?:jama|lancet|aaas|morandi)['\"]")
_PALETTE_SYSTEM_RE = re.compile(r"\b(?:PALETTE|COLORS|gallery_theme|palette_cmap|palette_stops)\b")
_EXPORT_CALL_RE = re.compile(r"\b(?:save_fig|savefig|save_plotly|write_image|write_html)\s*\(")


def extract_hardcoded_hex(src: str) -> tuple[list[tuple[int, str, str]], list[tuple[int, str, str]]]:
    """Return (all_hardcoded_hex_hits, non_grayscale_hex_hits) as (lineno, hex, line)."""
    all_hits: list[tuple[int, str, str]] = []
    non_gray: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(src.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        if _HEX_SKIP_RE.search(line):
            continue
        for match in _HEX_COLOR_RE.finditer(line):
            hx = match.group(1)
            item = (lineno, hx, line.strip())
            all_hits.append(item)
            if not _is_grayscale_hex(hx):
                non_gray.append(item)
    return all_hits, non_gray


def compute_log_span_orders(src: str) -> float:
    """Estimate maximum static log10 span on log-scaled x/y axes."""
    consts: dict[str, float] = {}
    for match in re.finditer(
        r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([0-9.]+e-?[0-9]+|[0-9.]+)\s*(?:#.*)?$",
        src,
        re.MULTILINE,
    ):
        try:
            consts[match.group(1)] = float(match.group(2))
        except ValueError:
            pass

    def _eval_tok(token: str) -> float | None:
        tok = token.strip()
        mul = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*\*\s*([0-9.]+(?:e-?[0-9]+)?)", tok)
        if mul and mul.group(1) in consts:
            return consts[mul.group(1)] * float(mul.group(2))
        if tok in consts:
            return consts[tok]
        try:
            return float(tok)
        except ValueError:
            return None

    best = 0.0
    for axis in ("x", "y"):
        if not re.search(rf"set_{axis}scale\(\s*['\"]log", src):
            continue
        for match in re.finditer(rf"set_{axis}lim\(\s*([^,)]+),\s*([^,)]+)\)", src):
            lo, hi = _eval_tok(match.group(1)), _eval_tok(match.group(2))
            if lo is not None and hi is not None and lo > 0 and hi > lo:
                best = max(best, math.log10(hi / lo))
    return best


def _utf8_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def enumerate_candidates(workspace: Path, script_dir: Path) -> tuple[list[Path], str | None]:
    style_review = script_dir / "recipe_style_review.py"
    if style_review.is_file():
        proc = subprocess.run(
            [sys.executable, str(style_review), "--workspace", str(workspace), "--list-candidates"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=_utf8_env(),
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()
            msg = "CRITICAL: failed to enumerate registered working scripts"
            if detail:
                msg += f" ({detail.splitlines()[-1]})"
            return [], msg
        paths: list[Path] = []
        for raw in proc.stdout.splitlines():
            cleaned = raw.strip()
            if not cleaned:
                continue
            p = Path(cleaned)
            if not p.is_absolute():
                p = workspace / p
            if p.is_file():
                paths.append(p.resolve())
        return paths, None
    return sorted(p.resolve() for p in workspace.glob("figures/gen_fig*.py") if p.is_file()), None


def load_tracked_baselines(workspace: Path) -> dict[Path, dict]:
    sources_dir = workspace / ".vivid" / "template-sources"
    tracked: dict[Path, dict] = {}
    if not sources_dir.is_dir():
        return tracked
    for rec_path in sorted(sources_dir.glob("*.json")):
        try:
            data = json.loads(rec_path.read_text(encoding="utf-8"))
            if data.get("schemaVersion") != 1:
                continue
            cand = (workspace / data["candidate"]).resolve()
            base_path = (workspace / data["baseline"]).resolve()
            if not base_path.is_file():
                continue
            base_code = base_path.read_text(encoding="utf-8", errors="replace")
            tracked[cand] = {
                "id": data.get("source", {}).get("id", ""),
                "codeSha256": data.get("source", {}).get("codeSha256", ""),
                "baseline_path": base_path,
                "baseline_code": base_code,
            }
        except Exception:
            continue
    return tracked


def _ast_symbols(tree: ast.AST) -> tuple[set[str], set[str], set[str]]:
    modules: set[str] = set()
    imported_names: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
                imported_names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    return modules, imported_names, calls


def inspect_script(path: Path, workspace: Path, tracked_info: dict | None) -> dict:
    bn = path.name
    try:
        rel = path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        rel = path.as_posix()

    critical: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    try:
        raw_code = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw_code = path.read_text(encoding="utf-8", errors="replace")

    code = raw_code.lstrip("\ufeff")

    try:
        tree = ast.parse(code, filename=str(path))
    except SyntaxError as exc:
        critical.append(
            f"CRITICAL {bn}: Python 语法错误 (line {exc.lineno}: {exc.msg}) — FIX: 修复语法错误后重新运行"
        )
        return {
            "script": rel,
            "name": bn,
            "kind": "invalid",
            "status": "critical",
            "critical": critical,
            "warnings": warnings,
            "infos": infos,
        }

    modules, imported_names, calls = _ast_symbols(tree)

    is_plotly = (
        any(m == "plotly" or m.startswith("plotly.") for m in modules)
        or "save_plotly" in imported_names
        or "save_plotly" in calls
        or "write_image" in calls
    )
    uses_gallery_theme = (
        any(m == "gallery_theme" or m.endswith(".gallery_theme") for m in modules)
        or bool(re.search(r"\bgallery_theme\b", code))
    )
    uses_setup_style = (
        "setup_style" in calls
        or "setup_style" in imported_names
        or bool(re.search(r"\bsetup_style\s*\(", code))
    )
    is_map = (
        "china_provinces.geojson" in code
        or any(m == "geopandas" or m.startswith("geopandas.") for m in modules)
    )
    uses_palette_system = uses_gallery_theme or bool(_PALETTE_SYSTEM_RE.search(code))

    is_registered = tracked_info is not None
    expected_sha = tracked_info.get("codeSha256", "") if tracked_info else ""
    is_unmodified_baseline = bool(
        is_registered
        and expected_sha
        and (
            _sha256_text(raw_code) == expected_sha
            or _sha256_text(raw_code.replace("\r\n", "\n")) == expected_sha
        )
    )

    if is_plotly:
        kind = "plotly"
    elif uses_gallery_theme:
        kind = "gallery"
    elif is_map:
        kind = "map"
    else:
        kind = "matplotlib"

    # 1. Theme / style initialization check
    if not is_plotly and not uses_setup_style and not uses_gallery_theme and not is_unmodified_baseline:
        critical.append(
            f"CRITICAL {bn}: missing setup_style() — figure will use default matplotlib styling — "
            f"FIX: add 'from _utils.plot_utils import setup_style; setup_style()' at top"
        )

    active_lines = [
        (lineno, line)
        for lineno, line in enumerate(code.splitlines(), 1)
        if not line.lstrip().startswith("#")
    ]

    # 2. Hardcoded ugly defaults & anti-patterns
    if any("1f77b4" in line.lower() for _, line in active_lines):
        critical.append(f"CRITICAL {bn}: matplotlib 默认蓝色 #1f77b4 — FIX: replace with PALETTE[0]")

    if any("RdYlGn" in line for _, line in active_lines):
        critical.append(
            f"CRITICAL {bn}: RdYlGn colormap (traffic light) — "
            f"FIX: use palette_cmap('diverging') or palette_cmap('sequential')"
        )

    if any(_RDBU_RE.search(line) for _, line in active_lines):
        critical.append(
            f"CRITICAL {bn}: RdBu/RdBu_r colormap is too dark — "
            f"FIX: use palette_cmap('diverging') or palette_cmap('sequential')"
        )

    if any(_DARK_THEME_RE.search(line) for _, line in active_lines):
        critical.append(
            f"CRITICAL {bn}: dark background theme — FIX: use setup_style() which sets white background"
        )

    if any(_PDF_LEAK_RE.search(line) for _, line in active_lines):
        critical.append(
            f"CRITICAL {bn}: .pdf suffix leaked into code (setup_style/path/label) — "
            f"remove .pdf from non-filename strings"
        )

    bright_hits = [
        line
        for _, line in active_lines
        if _BRIGHT_NAMED_RE.search(line) and not re.search(r"PALETTE|COLORS\[", line)
    ]
    if bright_hits:
        critical.append(
            f"CRITICAL {bn}: CSS 鲜艳命名色 (red/blue/green/orange/purple/brown) — "
            f"FIX: 用 PALETTE[n] 或 COLORS['up'/'down'/'highlight']"
        )

    # 3. Hardcoded hex colors check
    all_hc, non_gray_hc = extract_hardcoded_hex(code)
    base_all_hc, base_non_gray_hc = (
        extract_hardcoded_hex(tracked_info["baseline_code"]) if is_registered else ([], [])
    )
    if len(non_gray_hc) > 2:
        not_increased_above_baseline = is_registered and (
            len(non_gray_hc) <= len(base_non_gray_hc) or len(all_hc) <= len(base_all_hc)
        )
        if not_increased_above_baseline or is_map:
            infos.append(f"INFO {bn}: 保留模板/地图基线硬编码色值 ({len(non_gray_hc)} 处)")
        elif not uses_palette_system:
            critical.append(
                f"CRITICAL {bn}: 多个硬编码颜色 ({len(non_gray_hc)} 处) 绕过调色板且未使用 PALETTE/COLORS/gallery_theme — "
                f"FIX: 改用 PALETTE[n] / COLORS['up'/'down']"
            )
        else:
            infos.append(
                f"INFO {bn}: 含 {len(non_gray_hc)} 处自定义硬编码色值（已启用项目主题；可按需改用 PALETTE[n] / COLORS[...] 跟随调色板）"
            )
    elif len(non_gray_hc) > 0:
        infos.append(
            f"INFO {bn}: {len(non_gray_hc)} 个硬编码颜色（≤2 允许作局部高亮，建议优先用 COLORS['highlight'/'up'/'down']）"
        )

    # 4. Neutral named colors & advisory style hints
    if any(_NEUTRAL_NAMED_RE.search(line) and not re.search(r"PALETTE|COLORS\[", line) for _, line in active_lines):
        infos.append(f"INFO {bn}: gray/grey/black 中性色 — 可用，建议优先用 COLORS['ref_line'/'grid'/'text'] 跟随主题")

    if not is_unmodified_baseline:
        if any(_LEGACY_TONE_RE.search(line) for _, line in active_lines):
            warnings.append(f"WARNING {bn}: 检测到深沉旧版硬编码色值 — 建议改用 PALETTE[n] 或当前项目调色板")
        if any(_REMOVED_PALETTE_RE.search(line) for _, line in active_lines):
            warnings.append(
                f"WARNING {bn}: 使用了已移除的旧调色板名称 — 请使用 palettes.json 中的当前调色板"
            )

    if any(re.search(r"\bplt\.title\b|\.suptitle\s*\(", line) for _, line in active_lines):
        infos.append(f"INFO {bn}: 含整图标题；独立图片可保留，论文插图注意避免与图注重复")

    # 5. Export call check
    has_export = (
        bool({"save_fig", "savefig", "save_plotly", "write_image", "write_html"} & calls)
        or bool(_EXPORT_CALL_RE.search(code))
    )
    if not has_export:
        warnings.append(
            f"WARNING {bn}: 未检测到导出调用 (save_fig / savefig / save_plotly / write_image / write_html)"
        )

    # 6. Log-axis span check (> 4 orders of magnitude)
    log_span = compute_log_span_orders(code)
    if log_span > 4.0:
        warnings.append(
            f"WARNING {bn}: 对数轴跨了 {log_span:.1f} 个数量级 (>4) — 图边可能出现大片空白，请核对零值地板设置"
        )

    status = "critical" if critical else ("warning" if warnings else "ok")
    return {
        "script": rel,
        "name": bn,
        "kind": kind,
        "status": status,
        "critical": critical,
        "warnings": warnings,
        "infos": infos,
    }


def check_optional_plan(workspace: Path, candidates: list[Path], script_dir: Path) -> dict | None:
    """Optional silent check when FIGURE_PLAN.json or PAPER_PLAN.md is present."""
    fig_plan = workspace / "FIGURE_PLAN.json"
    paper_plan = workspace / "PAPER_PLAN.md"

    cand_names = {p.stem for p in candidates}
    fig_scripts = {p.stem for p in (workspace / "figures").glob("gen_fig*.py")} if (workspace / "figures").is_dir() else set()

    def _has_script(fig_id: str) -> bool:
        if f"gen_{fig_id}" in fig_scripts or fig_id in cand_names or f"gen_{fig_id}" in cand_names:
            return True
        if (workspace / "figures").is_dir() and any((workspace / "figures").glob(f"gen_{fig_id}*.py")):
            return True
        return any(fig_id in name for name in cand_names)

    if fig_plan.is_file():
        try:
            plan = json.loads(fig_plan.read_text(encoding="utf-8"))
            figures = [
                f["id"]
                for f in plan.get("figures", [])
                if isinstance(f, dict) and f.get("class") == "DATA" and isinstance(f.get("id"), str)
            ]
            missing = [fid for fid in figures if not _has_script(fid)]
            return {
                "plan_file": "FIGURE_PLAN.json",
                "planned_count": len(figures),
                "missing": missing,
                "audit_output": "",
            }
        except Exception as exc:
            return {
                "plan_file": "FIGURE_PLAN.json",
                "error": str(exc),
                "planned_count": 0,
                "missing": [],
                "audit_output": "",
            }

    if paper_plan.is_file():
        text = paper_plan.read_text(encoding="utf-8", errors="replace")
        planned = sorted(set(re.findall(r"\bfig_[A-Za-z0-9_]+\b", text)))
        missing = [fid for fid in planned if not _has_script(fid)]
        audit_out = ""
        recipe_audit = script_dir / "recipe_audit.py"
        if recipe_audit.is_file() and planned:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(recipe_audit),
                    "--plan",
                    str(paper_plan),
                    "--figdir",
                    str(workspace / "figures"),
                ],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env=_utf8_env(),
            )
            audit_out = (proc.stdout or "").strip()
        return {
            "plan_file": "PAPER_PLAN.md",
            "planned_count": len(planned),
            "missing": missing,
            "audit_output": audit_out,
        }

    return None


def run_source_review(workspace: Path, script_dir: Path) -> dict:
    sources_dir = workspace / ".vivid" / "template-sources"
    if not sources_dir.is_dir():
        return {
            "enabled": False,
            "ok": True,
            "summary": "INFO: no registered source baselines; source fidelity has not been checked.",
            "error": None,
        }

    style_review = script_dir / "recipe_style_review.py"
    if not style_review.is_file():
        return {
            "enabled": True,
            "ok": False,
            "summary": "",
            "error": "CRITICAL: cannot run registered source review (recipe_style_review.py unavailable)",
        }

    out_json = workspace / ".vivid" / "source-review.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(style_review),
            "--workspace",
            str(workspace),
            "--summary",
            "--output",
            str(out_json),
        ],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=_utf8_env(),
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        err = "CRITICAL: source record / source parse failure"
        if detail:
            err += f" ({detail.splitlines()[-1]})"
        return {
            "enabled": True,
            "ok": False,
            "summary": (proc.stdout or "").strip(),
            "error": err,
        }
    return {
        "enabled": True,
        "ok": True,
        "summary": (proc.stdout or "").strip(),
        "output": str(out_json),
        "error": None,
    }


def run_check(workspace: Path, script_dir: Path | None = None) -> dict:
    workspace = Path(workspace).resolve()
    script_dir = (script_dir or Path(__file__).resolve().parent).resolve()

    global_critical: list[str] = []
    candidates, enum_err = enumerate_candidates(workspace, script_dir)
    if enum_err:
        global_critical.append(enum_err)

    tracked = load_tracked_baselines(workspace)
    script_reports = [
        inspect_script(cand, workspace, tracked.get(cand.resolve()))
        for cand in candidates
    ]

    plan_report = check_optional_plan(workspace, candidates, script_dir)
    source_review = run_source_review(workspace, script_dir)
    if not source_review["ok"] and source_review.get("error"):
        global_critical.append(source_review["error"])

    violations = len(global_critical) + sum(len(r["critical"]) for r in script_reports)
    warnings = sum(len(r["warnings"]) for r in script_reports)
    infos = sum(len(r["infos"]) for r in script_reports)

    return {
        "workspace": str(workspace),
        "scanned_count": len(script_reports),
        "violations": violations,
        "warnings": warnings,
        "infos": infos,
        "global_critical": global_critical,
        "scripts": script_reports,
        "plan_check": plan_report,
        "source_review": source_review,
    }


def print_human_report(report: dict) -> None:
    print("=== 图表代码质量自检 ===")
    for msg in report["global_critical"]:
        if "enumerate" in msg:
            print(msg)
    print(f"实际扫描脚本: {report['scanned_count']}（完整组合走专用约定；来源核对另计）")

    for item in report["scripts"]:
        if item["status"] == "ok" and not item["infos"]:
            print(f"  [OK] {item['name']} ({item['kind']})")
        else:
            if item["status"] == "ok":
                print(f"  [OK] {item['name']} ({item['kind']})")
            for msg in item["critical"]:
                print(msg)
            for msg in item["warnings"]:
                print(msg)
            for msg in item["infos"]:
                print(msg)

    print(
        f"自检完成: {report['violations']} 个 CRITICAL（阻断） + "
        f"{report['warnings']} 个 WARNING（仅提醒，不阻断）"
    )

    plan = report.get("plan_check")
    if plan is not None:
        print("")
        print(f"=== 规划对照 ({plan['plan_file']}) ===")
        if plan.get("error"):
            print(f"WARNING: 无法解析 {plan['plan_file']}: {plan['error']}")
        else:
            missing = plan.get("missing", [])
            ready = plan["planned_count"] - len(missing)
            print(f"规划图表: {plan['planned_count']} 个 | 已就绪脚本: {ready} 个")
            for fid in missing:
                print(f"MISSING: {fid} — 规划中有但未找到对应脚本")
            if plan.get("audit_output"):
                print(plan["audit_output"])

    sr = report["source_review"]
    print("")
    if sr.get("summary"):
        print(sr["summary"])
    if not sr["ok"] and sr.get("error"):
        print(sr["error"])

    print("")
    print("==========================================")
    print(f"  总计: {report['violations']} 违规 + {report['warnings']} 警告 + {report['infos']} 提示")
    print("==========================================")


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = argparse.ArgumentParser(description="Vivid data figure static quality checker.")
    parser.add_argument("--workspace", default=".", help="Workspace root directory (default: .)")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args(argv)

    workspace = Path(args.workspace).resolve()
    if not workspace.is_dir():
        print(f"CRITICAL: workspace directory does not exist: {workspace}", file=sys.stderr)
        return 1

    report = run_check(workspace)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human_report(report)

    return min(report["violations"], 125)


if __name__ == "__main__":
    raise SystemExit(main())
