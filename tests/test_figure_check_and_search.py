"""Unit tests for cross-platform figure_check.py, figure_check.sh shim, search_figure.py, and requirements.txt."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "original/resources/assets/shared-scripts"
SCRIPTS = ROOT / "scripts"

if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import figure_check
from get_recipe import Recipes
import search_figure
from template_sources import digest, materialize


def _find_bash() -> str | None:
    if os.name == "nt":
        git_bash = Path("C:/Program Files/Git/bin/bash.exe")
        if git_bash.is_file():
            return str(git_bash)
    found = shutil.which("bash")
    return found if found and Path(found).exists() else None


class FigureCheckAndSearchTests(unittest.TestCase):
    def test_all_145_official_recipes_produce_zero_critical_violations(self):
        recipes = Recipes(SHARED)
        self.assertEqual(len(recipes.entries), 145)

        # 1. All 145 raw original.py recipes materialized as registered baselines
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            for tid in recipes.entries:
                code, source = recipes.script(tid)
                slug = tid.replace(".", "_")
                materialize(ws / "figures" / f"gen_fig_{slug}.py", code, source, ws)

            proc = subprocess.run(
                [sys.executable, "-B", str(SHARED / "figure_check.py"), "--workspace", str(ws), "--json"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["scanned_count"], 145)
            self.assertEqual(report["violations"], 0)
            for item in report["scripts"]:
                self.assertEqual(item["critical"], [], f"{item['name']} had critical findings: {item['critical']}")

        # 2. If working_script() is available, test all 145 working scripts both registered and unregistered
        if hasattr(recipes, "working_script"):
            with tempfile.TemporaryDirectory() as tmp_reg, tempfile.TemporaryDirectory() as tmp_unreg:
                ws_reg = Path(tmp_reg)
                ws_unreg = Path(tmp_unreg)
                (ws_unreg / "figures").mkdir(parents=True, exist_ok=True)
                for tid in recipes.entries:
                    code, source = recipes.working_script(tid)
                    slug = tid.replace(".", "_")
                    materialize(ws_reg / "figures" / f"gen_fig_{slug}.py", code, source, ws_reg)
                    (ws_unreg / "figures" / f"gen_fig_{slug}.py").write_text(code, encoding="utf-8")

                for ws in (ws_reg, ws_unreg):
                    report = figure_check.run_check(ws, SHARED)
                    self.assertEqual(report["scanned_count"], 145)
                    self.assertEqual(report["violations"], 0, f"Unexpected violations in {ws}: {report}")

    def test_script_archetypes_matplotlib_plotly_gallery_and_map(self):
        samples = {
            "gen_fig_mpl.py": (
                "from _utils.plot_utils import setup_style, save_fig, PALETTE\n"
                "import matplotlib.pyplot as plt\n"
                "setup_style()\n"
                "fig, ax = plt.subplots()\n"
                "ax.plot([1, 2], [3, 4], color=PALETTE[0])\n"
                "save_fig(fig, 'figures/out.pdf')\n"
            ),
            "gen_fig_plotly.py": (
                "from _utils.gallery_theme import P, C\n"
                "from _utils.plot_utils import save_plotly\n"
                "import plotly.graph_objects as go\n"
                "fig = go.Figure(go.Sunburst(labels=['A', 'B'], parents=['', 'A'], values=[10, 5]))\n"
                "save_plotly(fig, 'figures/sunburst.pdf')\n"
            ),
            "gen_fig_gallery.py": (
                "from _utils.gallery_theme import P, C, dark, palette_cmap\n"
                "import matplotlib.pyplot as plt\n"
                "fig, ax = plt.subplots()\n"
                "ax.bar([0, 1], [2, 3], color=C[:2])\n"
                "fig.savefig('figures/gallery.png')\n"
            ),
            "gen_fig_map.py": (
                "from _utils.plot_utils import setup_style, save_fig, PALETTE\n"
                "import geopandas as gpd\n"
                "setup_style()\n"
                "gdf = gpd.read_file('_utils/china_provinces.geojson')\n"
                "ax = gdf.plot(color='#F0F0F0', edgecolor='white')\n"
                "save_fig(ax.figure, 'figures/map.pdf')\n"
            ),
        }
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "figures").mkdir()
            for name, src in samples.items():
                (ws / "figures" / name).write_text(src, encoding="utf-8")

            report = figure_check.run_check(ws, SHARED)
            self.assertEqual(report["scanned_count"], 4)
            self.assertEqual(report["violations"], 0)
            by_name = {r["name"]: r for r in report["scripts"]}
            self.assertEqual(by_name["gen_fig_plotly.py"]["kind"], "plotly")
            self.assertEqual(by_name["gen_fig_gallery.py"]["kind"], "gallery")
            self.assertEqual(by_name["gen_fig_map.py"]["kind"], "map")
            self.assertEqual(by_name["gen_fig_mpl.py"]["kind"], "matplotlib")

    def test_genuine_violations_return_nonzero_exit_code(self):
        bad_cases = {
            "default_blue": (
                "from _utils.plot_utils import setup_style, save_fig\n"
                "setup_style()\n"
                "ax.plot(x, y, color='#1f77b4')\n"
                "save_fig(fig, 'figures/a.pdf')\n"
            ),
            "traffic_light": (
                "from _utils.plot_utils import setup_style, save_fig\n"
                "setup_style()\n"
                "ax.imshow(z, cmap='RdYlGn')\n"
                "save_fig(fig, 'figures/a.pdf')\n"
            ),
            "dark_rdbu": (
                "from _utils.plot_utils import setup_style, save_fig\n"
                "setup_style()\n"
                "ax.imshow(z, cmap='RdBu_r')\n"
                "save_fig(fig, 'figures/a.pdf')\n"
            ),
            "dark_theme": (
                "from _utils.plot_utils import setup_style, save_fig\n"
                "import matplotlib.pyplot as plt\n"
                "plt.style.use('dark_background')\n"
                "setup_style()\n"
                "save_fig(fig, 'figures/a.pdf')\n"
            ),
            "bright_named": (
                "from _utils.plot_utils import setup_style, save_fig\n"
                "setup_style()\n"
                "ax.plot(x, y, color='red')\n"
                "save_fig(fig, 'figures/a.pdf')\n"
            ),
            "many_unpaletted_hex": (
                "from _utils.plot_utils import setup_style, save_fig\n"
                "setup_style()\n"
                "ax.plot(x, y1, color='#e41a1c')\n"
                "ax.plot(x, y2, color='#377eb8')\n"
                "ax.plot(x, y3, color='#4daf4a')\n"
                "save_fig(fig, 'figures/a.pdf')\n"
            ),
            "missing_setup_style": (
                "import matplotlib.pyplot as plt\n"
                "fig, ax = plt.subplots()\n"
                "ax.plot([1, 2], [3, 4])\n"
                "fig.savefig('figures/a.png')\n"
            ),
            "syntax_error": (
                "from _utils.plot_utils import setup_style\n"
                "def broken(\n"
            ),
        }

        for label, code in bad_cases.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp:
                ws = Path(tmp)
                (ws / "figures").mkdir()
                (ws / "figures" / "gen_fig_bad.py").write_text(code, encoding="utf-8")
                proc = subprocess.run(
                    [sys.executable, "-B", str(SHARED / "figure_check.py"), "--workspace", str(ws)],
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                )
                self.assertNotEqual(proc.returncode, 0, f"Expected non-zero for {label}, got:\n{proc.stdout}")
                self.assertIn("CRITICAL", proc.stdout)

    def test_python_cli_and_bash_shim_and_optional_plan(self):
        code = (
            "from _utils.plot_utils import setup_style, save_fig, PALETTE\n"
            "import matplotlib.pyplot as plt\n"
            "setup_style()\n"
            "FLOOR = 1e-4\n"
            "fig, ax = plt.subplots()\n"
            "ax.set_xscale('log')\n"
            "ax.set_xlim(FLOOR, 1000)\n"
            "ax.plot([1, 10], [2, 20], color=PALETTE[0])\n"
            "save_fig(fig, 'figures/custom.pdf')\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ws / "figures" / "custom-name.py"
            rec = materialize(target, code, {"id": "basic.line", "variant": "test", "codeSha256": digest(code)}, ws)

            proc_py = subprocess.run(
                [sys.executable, "-B", str(SHARED / "figure_check.py"), "--workspace", str(ws)],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(proc_py.returncode, 0, proc_py.stdout + proc_py.stderr)
            self.assertIn("实际扫描脚本: 1", proc_py.stdout)
            self.assertIn("custom-name.py", proc_py.stdout)
            self.assertIn("对数轴跨了 7.0 个数量级", proc_py.stdout)
            self.assertNotIn("TOPIC_PLAN.md", proc_py.stdout)
            self.assertTrue((ws / ".vivid" / "source-review.json").is_file())

            bash = _find_bash()
            if bash:
                env = dict(os.environ, VIVID_PYTHON=sys.executable, PYTHONUTF8="1")
                proc_sh = subprocess.run(
                    [bash, str(SHARED / "figure_check.sh")],
                    cwd=ws,
                    env=env,
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                )
                self.assertEqual(proc_sh.returncode, 0, proc_sh.stdout + proc_sh.stderr)
                self.assertIn("实际扫描脚本: 1", proc_sh.stdout)
                self.assertIn("custom-name.py", proc_sh.stdout)

            # Optional FIGURE_PLAN.json check when present
            (ws / "FIGURE_PLAN.json").write_text(
                json.dumps({"figures": [{"id": "fig_missing_demo", "class": "DATA"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            report_plan = figure_check.run_check(ws, SHARED)
            self.assertIsNotNone(report_plan["plan_check"])
            self.assertIn("fig_missing_demo", report_plan["plan_check"]["missing"])

            # Tampering saved baseline triggers CRITICAL via recipe_style_review
            Path(rec["record"]).with_suffix(".py").write_text("# tampered\n", encoding="utf-8")
            proc_tamper = subprocess.run(
                [sys.executable, "-B", str(SHARED / "figure_check.py"), "--workspace", str(ws)],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertNotEqual(proc_tamper.returncode, 0)

    def test_search_figure_queries_categories_and_json_cli(self):
        entries = search_figure.load_entries()
        self.assertEqual(len(entries), 148)

        # 1. SHAP 特征归因
        shap_res = search_figure.rank("SHAP 特征归因", entries=entries, limit=5)
        shap_ids = [r["id"] for r in shap_res]
        self.assertIn("advanced.shap_summary", shap_ids[:3])
        self.assertTrue(
            "template.shap_dependence" in shap_ids[:4] or "template.shap_contribution" in shap_ids[:4]
        )

        # 2. raincloud distribution
        rc_res = search_figure.rank("raincloud distribution", entries=entries, limit=5)
        self.assertEqual(rc_res[0]["id"], "basic.raincloud")
        self.assertIn("empirical.raincloud", [r["id"] for r in rc_res])

        # 3. 弦图
        chord_res = search_figure.rank("弦图", entries=entries, limit=5)
        self.assertEqual(chord_res[0]["id"], "screenshot.chord")

        # 4. 3d surface
        surf_res = search_figure.rank("3d surface", entries=entries, limit=5)
        surf_ids = {r["id"] for r in surf_res}
        self.assertIn("competition.surface_3d", surf_ids)
        self.assertIn("screenshot.mesh_surface_3d", surf_ids)

        # 5. Category filter + --json + --limit via CLI
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(SCRIPTS / "search_figure.py"),
                "3d surface",
                "--category",
                "3d",
                "--limit",
                "3",
                "--json",
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(len(payload), 3)
        for item in payload:
            self.assertTrue(item["card"].startswith("catalog/cards/"))
            self.assertTrue(item["preview_path"].startswith("catalog/previews/"))
            self.assertGreater(item["score"], 0)

        # Human-readable CLI check
        proc_txt = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS / "search_figure.py"), "弦图", "--limit", "2"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(proc_txt.returncode, 0)
        self.assertIn("screenshot.chord", proc_txt.stdout)
        self.assertIn("catalog/cards/screenshot.chord.md", proc_txt.stdout)
        self.assertIn("catalog/previews/screenshot.chord-1.png", proc_txt.stdout)

    def test_requirements_txt_synced(self):
        req_lines = [
            line.strip()
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        req_names = {line.split(">=")[0].split("==")[0].strip() for line in req_lines}

        for added in ("plotly", "kaleido", "pycirclize", "Faker", "scikit-image"):
            self.assertIn(added, req_names)
        for removed in ("python-docx", "PyPDF2", "pypdf", "pdf2image", "sympy", "statsmodels"):
            self.assertNotIn(removed, req_names)
        self.assertIn("-r requirements-architecture.txt", req_lines)


if __name__ == "__main__":
    unittest.main()
