"""Runtime, provenance, palette/language, and visual regression tests for Skill recipes."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import matplotlib
matplotlib.use('Agg')
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / 'original/resources/assets/shared-scripts'
sys.path.insert(0, str(SHARED))

import plot_utils as pu
import vivid_config as vc
from figure_language import apply_figure_fonts
from get_recipe import Recipes
from recipe_style_review import compare_sources
from template_sources import digest, materialize, read_record


def _prepare_workspace(ws: Path) -> Path:
    utils = ws / '_utils'
    utils.mkdir(parents=True, exist_ok=True)
    (ws / '.vivid').mkdir(parents=True, exist_ok=True)
    for item in SHARED.iterdir():
        if item.is_file() and item.suffix not in {'.enc', '.pyc'}:
            shutil.copy2(item, utils / item.name)
    (ws / '.vivid/runtime.json').write_text(
        json.dumps({'runtime_skill': str(ROOT / 'original/resources')}),
        encoding='utf-8',
    )
    vc.write_config(ws)
    return utils


def _pdf_text(path: Path) -> str:
    import fitz
    with fitz.open(path) as doc:
        return '\n'.join(page.get_text() for page in doc)


class ScreenshotSkillRuntimeTests(unittest.TestCase):
    def tearDown(self):
        plt.close('all')

    def test_plot_utils_cleanup_and_workbench_sync(self):
        wb_copy = ROOT / 'workbench/editor_backend/_utils/plot_utils.py'
        self.assertEqual((SHARED / 'plot_utils.py').read_bytes(), wb_copy.read_bytes())
        self.assertEqual(
            (SHARED / 'english-labels.json').read_bytes(),
            (ROOT / 'workbench/assets/english-labels.json').read_bytes(),
        )
        self.assertIn('get_recipe.py', pu.__doc__ or '')
        self.assertNotIn('forest_plot', pu.__doc__ or '')

        removed = (
            '_hook_savefig', '_guard_subplot_size', '_auto_fix_overlaps',
            '_ensure_ticklabels_visible', '_pull_back_outside_transaxes_text',
            '_auto_shrink_figsize_if_sparse', '_simple_spread',
            'forest_plot', 'trend_plot', 'bar_compare', 'distribution_plot',
            'scatter_plot', 'residual_diagnostic', 'multi_line_plot',
            'box_plot', 'radar_plot', 'subplot_grid',
        )
        for name in removed:
            self.assertFalse(hasattr(pu, name), f'{name} should be removed from plot_utils')

        kept = (
            'setup_style', 'save_fig', 'save_plotly', 'PALETTE', 'PALETTE_LIGHT',
            'COLORS', '_lighten', 'heatmap', 'smart_labels', 'auto_legend',
            'auto_truncate_yticklabels', 'check_legend_overlap',
            '_has_3d_axes', '_onscreen_tick_labels',
            '_warn_if_wasted_margin', '_warn_if_data_clipped',
        )
        for name in kept:
            self.assertTrue(hasattr(pu, name), f'{name} must remain on plot_utils')

    def test_gallery_theme_supports_package_and_direct_imports(self):
        with tempfile.TemporaryDirectory(prefix='vivid-gallery-theme-') as tmp:
            ws = Path(tmp)
            utils = _prepare_workspace(ws)
            for palette in ('olive-apricot', 'blue-pink'):
                vc.write_config(ws, palette=palette)
                expected_p = vc.palette_colors(vc.load_config(ws))
                expected_c = vc.categorical_colors(vc.load_config(ws))
                for import_stmt, py_path in (
                    ('from _utils.gallery_theme import P, C, dark, palette_cmap, palette_stops', str(ws)),
                    ('from gallery_theme import P, C, dark, palette_cmap, palette_stops', str(utils)),
                ):
                    env = dict(os.environ, PYTHONPATH=py_path, VIVID_WORKSPACE=str(ws))
                    probe = (
                        f"{import_stmt}\n"
                        "import json\n"
                        "print(json.dumps({'P': P[:len(P)], 'C': C[:len(C)], "
                        "'dark': dark(P[0]), 'stops': palette_stops('diverging', count=3)}))\n"
                    )
                    res = subprocess.run(
                        [sys.executable, '-B', '-c', probe],
                        cwd=ws, env=env, capture_output=True, encoding='utf-8', check=True,
                    )
                    payload = json.loads(res.stdout)
                    self.assertGreaterEqual(len(payload['P']), 8)
                    self.assertGreaterEqual(len(payload['C']), 8)
                    self.assertEqual(payload['P'][:len(expected_p)], expected_p)
                    self.assertEqual(payload['C'][:len(expected_c)], expected_c)
                    self.assertEqual(len(payload['stops']), 3)

    def test_all_32_screenshot_working_scripts_parse_materialize_and_review_cleanly(self):
        recipes = Recipes(SHARED)
        cards = {
            c['id']: c
            for c in json.loads((ROOT / 'catalog/cards.json').read_text(encoding='utf-8'))['cards']
        }
        ss_map = json.loads((SHARED / 'screenshot_skill_sources.json').read_text(encoding='utf-8'))
        screenshot_ids = sorted(k for k in recipes.entries if k.startswith('screenshot.'))
        self.assertEqual(len(screenshot_ids), 32)
        self.assertEqual(sorted(ss_map), screenshot_ids)

        mpl_count = 0
        plotly_count = 0
        with tempfile.TemporaryDirectory(prefix='vivid-ss-contracts-') as tmp:
            ws = Path(tmp)
            _prepare_workspace(ws)
            for tid in screenshot_ids:
                with self.subTest(tid=tid):
                    # Primary Recipes.script() remains unchanged for catalog provenance
                    orig_code, orig_source = recipes.script(tid)
                    self.assertEqual(
                        orig_code.strip(),
                        (ROOT / 'catalog' / cards[tid]['source']['original_code']).read_text(encoding='utf-8').strip(),
                    )

                    code, source = recipes.working_script(tid)
                    ast.parse(code)
                    self.assertIn('from _utils.gallery_theme import P, C, dark, palette_cmap, palette_stops', code)
                    self.assertNotIn('.show(', code)
                    self.assertNotIn('Microsoft YaHei', code)
                    self.assertEqual(source['codeSha256'], digest(code))
                    self.assertEqual(source['originCodeSha256'], orig_source['codeSha256'])
                    self.assertNotEqual(source['codeSha256'], source['originCodeSha256'])

                    slug = tid.split('.', 1)[1]
                    if 'plotly.graph_objects' in code:
                        plotly_count += 1
                        self.assertIn('from _utils.plot_utils import save_plotly', code)
                        self.assertIn(f"save_plotly(fig, 'figures/fig_{slug}.pdf')", code)
                    else:
                        mpl_count += 1
                        self.assertIn('from _utils.plot_utils import setup_style, save_fig', code)
                        self.assertIn('setup_style()', code)
                        self.assertIn(f"save_fig(fig, 'figures/fig_{slug}.pdf')", code)

                    target = ws / 'figures' / f"gen_{tid.replace('.', '_')}.py"
                    info = materialize(target, code, source, ws)
                    self.assertEqual(info['status'], 'created')
                    record_data, baseline = read_record(info['record'], ws)
                    self.assertEqual(record_data['source']['originCodeSha256'], orig_source['codeSha256'])
                    review = compare_sources(baseline, target.read_text(encoding='utf-8'))
                    self.assertEqual(review['findings'], [])

            self.assertEqual(mpl_count, 22)
            self.assertEqual(plotly_count, 10)

            # CLI --id/--script and --plan/--scripts-dir use working_script()
            cli_target = ws / 'cli_figures/chord.py'
            res = subprocess.run(
                [sys.executable, '-B', str(ws / '_utils/get_recipe.py'),
                 '--id', 'screenshot.chord', '--script', str(cli_target), '--workspace', str(ws)],
                cwd=ws, capture_output=True, encoding='utf-8', check=True,
            )
            self.assertEqual(json.loads(res.stdout)['template'], 'screenshot.chord')
            self.assertEqual(cli_target.read_text(encoding='utf-8'), ss_map['screenshot.chord'])

            plan = ws / 'plan.md'
            plan.write_text('recipe:basic.grouped_bar recipe:screenshot.sunburst\n', encoding='utf-8')
            batch_dir = ws / 'batch_figures'
            subprocess.run(
                [sys.executable, '-B', str(ws / '_utils/get_recipe.py'),
                 '--plan', str(plan), '--scripts-dir', str(batch_dir), '--workspace', str(ws)],
                cwd=ws, capture_output=True, encoding='utf-8', check=True,
            )
            self.assertEqual(
                (batch_dir / 'gen_fig_screenshot_sunburst.py').read_text(encoding='utf-8'),
                ss_map['screenshot.sunburst'],
            )

    def test_matplotlib_runtime_zh_en_palettes_formats_and_zero_visual_regression(self):
        with tempfile.TemporaryDirectory(prefix='vivid-mpl-runtime-') as tmp:
            ws = Path(tmp)
            _prepare_workspace(ws)
            env = dict(os.environ, PYTHONPATH=str(ws), VIVID_WORKSPACE=str(ws), PYTHONDONTWRITEBYTECODE='1')

            for tid in ('basic.grouped_bar', 'screenshot.chord', 'screenshot.radial_bars'):
                script_path = ws / 'figures' / f"gen_{tid.replace('.', '_')}.py"
                subprocess.run(
                    [sys.executable, '-B', str(ws / '_utils/get_recipe.py'),
                     '--id', tid, '--script', str(script_path), '--workspace', str(ws)],
                    cwd=ws, env=env, capture_output=True, encoding='utf-8', check=True,
                )

            # 1) zh + olive-apricot vs blue-pink
            vc.write_config(ws, language='zh', palette='olive-apricot')
            for tid, out_name, expected_zh in (
                ('basic.grouped_bar', 'fig_grouped_bar.pdf', '指标A'),
                ('screenshot.chord', 'fig_chord.pdf', '基因关联弦图'),
                ('screenshot.radial_bars', 'fig_radial_bars.pdf', '径向柱状图'),
            ):
                script_path = ws / 'figures' / f"gen_{tid.replace('.', '_')}.py"
                subprocess.run([sys.executable, '-B', str(script_path)], cwd=ws, env=env, check=True, capture_output=True)
                out_pdf = ws / 'figures' / out_name
                self.assertTrue(out_pdf.is_file() and out_pdf.stat().st_size > 2000)
                text_zh = _pdf_text(out_pdf)
                self.assertIn(expected_zh, text_zh)

            olive_radial_bytes = (ws / 'figures/fig_radial_bars.pdf').read_bytes()
            vc.write_config(ws, language='zh', palette='blue-pink')
            subprocess.run(
                [sys.executable, '-B', str(ws / 'figures/gen_screenshot_radial_bars.py')],
                cwd=ws, env=env, check=True, capture_output=True,
            )
            blue_radial_bytes = (ws / 'figures/fig_radial_bars.pdf').read_bytes()
            self.assertNotEqual(olive_radial_bytes, blue_radial_bytes)

            # 2) Zero visual regression guarantee for classic zh recipe output
            vc.write_config(ws, language='zh', palette='olive-apricot')
            grouped_code = (ws / 'figures/gen_basic_grouped_bar.py').read_text(encoding='utf-8')
            via_save_fig = ws / 'figures/grouped_via_save_fig.png'
            via_direct = ws / 'figures/grouped_direct_baseline.png'
            (ws / 'run_save_fig.py').write_text(
                grouped_code.replace("'figures/fig_grouped_bar.pdf'", f"r'{via_save_fig}'"),
                encoding='utf-8',
            )
            direct_tail = (
                "from _utils.figure_language import apply_figure_fonts\n"
                "apply_figure_fonts(fig, 'zh')\n"
                f"fig.savefig(r'{via_direct}', format='png', pad_inches=0.15, bbox_inches=None, dpi=350)\n"
                "plt.close(fig)\n"
            )
            (ws / 'run_direct.py').write_text(
                grouped_code.replace("save_fig(fig, 'figures/fig_grouped_bar.pdf')", direct_tail),
                encoding='utf-8',
            )
            subprocess.run([sys.executable, '-B', str(ws / 'run_save_fig.py')], cwd=ws, env=env, check=True, capture_output=True)
            subprocess.run([sys.executable, '-B', str(ws / 'run_direct.py')], cwd=ws, env=env, check=True, capture_output=True)
            self.assertEqual(via_save_fig.read_bytes(), via_direct.read_bytes())
            np.testing.assert_array_equal(mpimg.imread(via_save_fig), mpimg.imread(via_direct))

            # 3) en automatic translation via save_fig + custom english_labels + multi-format export
            vc.write_config(ws, language='en', palette='olive-apricot', english_labels={'自定义组': 'Custom Cohort'})
            for tid, out_name, expected_en, forbidden_zh in (
                ('basic.grouped_bar', 'fig_grouped_bar.pdf', ('Metric A', 'Our method', 'Score'), '指标A'),
                ('screenshot.chord', 'fig_chord.pdf', ('Gene links', 'Gene A'), '基因关联弦图'),
                ('screenshot.radial_bars', 'fig_radial_bars.pdf', ('Radial bar chart', 'Low', 'Medium', 'High'), '径向柱状图'),
            ):
                script_path = ws / 'figures' / f"gen_{tid.replace('.', '_')}.py"
                subprocess.run([sys.executable, '-B', str(script_path)], cwd=ws, env=env, check=True, capture_output=True)
                text_en = _pdf_text(ws / 'figures' / out_name)
                for phrase in expected_en:
                    self.assertIn(phrase, text_en)
                self.assertNotIn(forbidden_zh, text_en)

            multi_script = ws / 'run_multi_formats.py'
            multi_script.write_text(
                "import matplotlib.pyplot as plt\n"
                "from _utils.plot_utils import setup_style, save_fig\n"
                "setup_style()\n"
                "fig, ax = plt.subplots(figsize=(4, 3))\n"
                "ax.plot([0, 1], [1, 2], label='自定义组')\n"
                "ax.set_xlabel('年份')\n"
                "ax.legend()\n"
                "save_fig(fig, 'figures/multi_fmt.pdf', formats=('pdf', 'png'))\n"
                "assert getattr(fig, '_vivid_localized_en', False) is True\n",
                encoding='utf-8',
            )
            subprocess.run([sys.executable, '-B', str(multi_script)], cwd=ws, env=env, check=True, capture_output=True)
            self.assertTrue((ws / 'figures/multi_fmt.pdf').is_file() and (ws / 'figures/multi_fmt.pdf').stat().st_size > 1000)
            self.assertTrue((ws / 'figures/multi_fmt.png').is_file() and (ws / 'figures/multi_fmt.png').stat().st_size > 1000)
            multi_pdf_text = _pdf_text(ws / 'figures/multi_fmt.pdf')
            self.assertIn('Custom Cohort', multi_pdf_text)
            self.assertIn('Year', multi_pdf_text)

    def test_plotly_runtime_save_plotly_zh_en_palettes_and_formats(self):
        try:
            import plotly.graph_objects as go  # noqa: F401
        except ImportError:
            self.skipTest('Plotly is optional')

        with tempfile.TemporaryDirectory(prefix='vivid-plotly-runtime-') as tmp:
            ws = Path(tmp)
            _prepare_workspace(ws)
            env = dict(os.environ, PYTHONPATH=str(ws), VIVID_WORKSPACE=str(ws), PYTHONDONTWRITEBYTECODE='1')

            for tid in ('screenshot.isosurface', 'screenshot.spiral_bubbles_3d'):
                script_path = ws / 'figures' / f"gen_{tid.replace('.', '_')}.py"
                subprocess.run(
                    [sys.executable, '-B', str(ws / '_utils/get_recipe.py'),
                     '--id', tid, '--script', str(script_path), '--workspace', str(ws)],
                    cwd=ws, env=env, capture_output=True, encoding='utf-8', check=True,
                )

            # Run screenshot.isosurface in zh (writes PDF via save_plotly)
            vc.write_config(ws, language='zh', palette='olive-apricot')
            subprocess.run(
                [sys.executable, '-B', str(ws / 'figures/gen_screenshot_isosurface.py')],
                cwd=ws, env=env, check=True, capture_output=True,
            )
            iso_pdf = ws / 'figures/fig_isosurface.pdf'
            self.assertTrue(iso_pdf.is_file() and iso_pdf.stat().st_size > 2000)

            # Multi-format + palette + zh/en localization check on screenshot.spiral_bubbles_3d (has 'Z 值')
            spiral_src = (ws / 'figures/gen_screenshot_spiral_bubbles_3d.py').read_text(encoding='utf-8')
            spiral_multi = ws / 'figures/run_spiral_multi.py'
            spiral_multi.write_text(
                spiral_src.replace(
                    "save_plotly(fig, 'figures/fig_spiral_bubbles_3d.pdf')",
                    "save_plotly(fig, 'figures/fig_spiral_bubbles_3d', formats=('pdf', 'png', 'html'))",
                ),
                encoding='utf-8',
            )
            subprocess.run([sys.executable, '-B', str(spiral_multi)], cwd=ws, env=env, check=True, capture_output=True)
            for ext in ('pdf', 'png', 'html'):
                out = ws / 'figures' / f'fig_spiral_bubbles_3d.{ext}'
                self.assertTrue(out.is_file() and out.stat().st_size > 1000, f'Missing {out}')
            zh_html = (ws / 'figures/fig_spiral_bubbles_3d.html').read_text(encoding='utf-8')
            olive_first = vc.palette_colors(vc.load_config(ws))[0]
            self.assertIn(olive_first.lower(), zh_html.lower())
            self.assertIn('Z 值', zh_html)

            # Switch to English + blue-pink palette
            vc.write_config(ws, language='en', palette='blue-pink')
            subprocess.run([sys.executable, '-B', str(spiral_multi)], cwd=ws, env=env, check=True, capture_output=True)
            en_html = (ws / 'figures/fig_spiral_bubbles_3d.html').read_text(encoding='utf-8')
            blue_first = vc.palette_colors(vc.load_config(ws))[0]
            self.assertIn(blue_first.lower(), en_html.lower())
            self.assertIn('Z value', en_html)
            self.assertNotIn('Z 值', en_html)
            self.assertIn('Z value', _pdf_text(ws / 'figures/fig_spiral_bubbles_3d.pdf'))


if __name__ == '__main__':
    unittest.main()
