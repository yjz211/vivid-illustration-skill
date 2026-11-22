#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学术级图表工具库 — 统一风格、配色、字体与多语言导出运行时。

使用方式（工作脚本应通过 `_utils/get_recipe.py` 从模板配方准备，而非调用旧黑盒包装函数）：
    from _utils.plot_utils import setup_style, save_fig, PALETTE, COLORS, _lighten
    setup_style()  # 初始化学术风格
    ...
    save_fig(fig, 'figures/fig_result.pdf')
"""
import os
import operator
import sys
import platform
import numpy as np
try:
    from . import vivid_config as vc
    from .figure_language import font_candidates, apply_figure_fonts, localize_figure, translate_text
except ImportError:
    import vivid_config as vc
    from figure_language import font_candidates, apply_figure_fonts, localize_figure, translate_text

# 延迟导入 matplotlib，避免在没有 GUI 的环境报错
_plt = None
_sns = None

def _get_plt():
    global _plt
    if _plt is None:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        _plt = plt
    return _plt

def _get_sns():
    global _sns
    if _sns is None:
        try:
            import seaborn as sns
            _sns = sns
        except ImportError:
            _sns = None
    return _sns


# ============================================================
# 学术配色方案
# ============================================================
class _Palette(list):
    """Keep the supplied colors, cycling positive indices for template roles.

    Templates can request a third or fourth category even with a two-color
    custom palette. Iteration, length, slices, and negative indices retain
    normal list behavior, so color scales still see only the supplied colors.
    """

    def __getitem__(self, key):
        if not isinstance(key, slice):
            key = operator.index(key)
            if self and key >= len(self):
                key %= len(self)
        return super().__getitem__(key)


# All user palette definitions are maintained in palettes.json.
_registry = vc.registry()
PALETTES = {k: vc.categorical_colors({'palette': k}) for k in _registry['palettes']}
PALETTE = _Palette(vc.categorical_colors())
PALETTE_LIGHT = None  # 延迟初始化，在 _lighten 定义后赋值

COLORS = {
    'primary': PALETTE[0] if len(PALETTE)>0 else PALETTE[0],
    'secondary': PALETTE[1] if len(PALETTE)>1 else PALETTE[0],
    'accent': PALETTE[2] if len(PALETTE)>2 else PALETTE[0],
    'gray': '#B8B8B8',
    'light': '#F5F7FA',
    'dark': '#2D2D2D',
    # 语义颜色
    'up': PALETTE[2] if len(PALETTE)>2 else PALETTE[0],
    'down': PALETTE[1] if len(PALETTE)>1 else PALETTE[0],
    'neutral': '#B8B8B8',     # 中性
    'highlight': PALETTE[4] if len(PALETTE)>4 else PALETTE[0],
    'ref_line': '#AAAAAA',    # 参考线
    'grid': '#E0E0E0',        # 网格线（很淡）
    'text': '#4A4A4A',        # 标注文字
    'bg_box': '#F5F7FA',      # 标注框背景
    'bg_fill': None,
    'bg_fill2': None,
}


def _read_palette_marker():
    return vc.load_config()['palette']


def _read_custom_colors():
    return vc.palette_colors()


def _read_style_marker():
    style = vc.load_config()['style']
    if style not in STYLE_FAMILIES:
        raise ValueError(f'Unknown Vivid layout: {style}')
    return style


# 「高级自定义版式」约束档位 —— 每个维度只给几个安全值(取自 STYLE_FAMILIES 验证过的值域),
# 用户任意组合都不会配出丑图。前端/后端/本文件三处的档位键必须一致。
_STYLE_CUSTOM_DIMS = {
    'frame': ('open', 'journal'),          # 边框:极简左下 / 期刊四面
    'grid': ('none', 'y', 'both'),         # 网格:无 / 横向淡 / 全网格淡
    'lw': ('thin', 'mid', 'thick'),        # 线宽:细 / 中 / 粗
    'font': ('small', 'medium', 'large'),  # 字号:小 / 中 / 大(全局 rcParams,必生效)
    'legend': ('noframe', 'framed'),       # 图例:无框 / 有框
    'bg': ('white', 'graytint'),           # 背景:纯白 / 淡灰底
}


def _read_style_custom_marker():
    spec = vc.load_config().get('style_custom')
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise ValueError('style_custom must be an object')
    for key, value in spec.items():
        if key not in _STYLE_CUSTOM_DIMS or value not in _STYLE_CUSTOM_DIMS[key]:
            raise ValueError(f'Invalid layout setting: {key}={value}')
    return {key: spec.get(key, allowed[0]) for key, allowed in _STYLE_CUSTOM_DIMS.items()}


# ============================================================
# 「成品风格族」—— 每套是一组经审美验证、彼此自洽的完整版式参数。
# 项目配置选择一套完整参数，也可按用户要求使用自定义版式。
# 关键：每套都【显式控制刻度四面】，tick_tr=False 时关掉上/右刻度 = 消灭“上右黑点点”。
# ============================================================
STYLE_FAMILIES = {
    'clean_open':     {'spines': ('left', 'bottom'), 'tick_dir': 'out', 'tick_tr': False,
                       'grid': None, 'legend_frame': False, 'patch_edge': 'white',
                       'lw': 1.8, 'ms': 5, 'axis_color': '#666666'},
    'soft_grid':      {'spines': ('left', 'bottom'), 'tick_dir': 'out', 'tick_tr': False,
                       'grid': {'axis': 'y', 'ls': '--', 'alpha': 0.30, 'color': '#CCCCCC'},
                       'legend_frame': False, 'patch_edge': 'white', 'lw': 1.9, 'ms': 5, 'axis_color': '#666666'},
    'framed_journal': {'spines': ('left', 'bottom', 'top', 'right'), 'tick_dir': 'in', 'tick_tr': True,
                       'grid': {'axis': 'both', 'ls': '-', 'alpha': 0.15, 'color': '#DDDDDD'},
                       'legend_frame': True, 'patch_edge': 'white', 'lw': 1.7, 'ms': 4.5, 'axis_color': '#444444'},
    'minimal_bare':   {'spines': ('left', 'bottom'), 'tick_dir': 'out', 'tick_tr': False,
                       'grid': None, 'legend_frame': False, 'patch_edge': 'none',
                       'lw': 2.0, 'ms': 6, 'axis_color': '#888888'},
    'bold_edge':      {'spines': ('left', 'bottom'), 'tick_dir': 'out', 'tick_tr': False,
                       'grid': None, 'legend_frame': False, 'patch_edge': 'white_bold',
                       'lw': 2.1, 'ms': 6, 'axis_color': '#555555'},
    'crisp_dark':     {'spines': ('left', 'bottom', 'top', 'right'), 'tick_dir': 'in', 'tick_tr': True,
                       'grid': None, 'legend_frame': True, 'patch_edge': 'white',
                       'lw': 1.8, 'ms': 5, 'axis_color': '#333333'},
}
_STYLE_FAMILY_NAMES = list(STYLE_FAMILIES.keys())




def _knobs_from_custom(spec):
    """把「高级自定义」档位 {frame,grid,lw} 映射成完整 knobs（唯一真相源:
    预生成预览图 与 实际出图 都调本函数，杜绝"预览≠实际"）。
    所有取值来自 STYLE_FAMILIES 验证过的值域，任意组合都自洽好看。
    未开放的维度（描边等）用安全固定值。"""
    _frame = {
        'open':    {'spines': ('left', 'bottom'),               'tick_dir': 'out', 'tick_tr': False,
                    'legend_frame': False, 'axis_color': '#666666'},
        'journal': {'spines': ('left', 'bottom', 'top', 'right'), 'tick_dir': 'in',  'tick_tr': True,
                    'legend_frame': True,  'axis_color': '#444444'},
    }
    _grid = {
        'none': None,
        'y':    {'axis': 'y',    'ls': '--', 'alpha': 0.30, 'color': '#CCCCCC'},
        'both': {'axis': 'both', 'ls': '-',  'alpha': 0.15, 'color': '#DDDDDD'},
    }
    _lw = {'thin': (1.7, 4.5), 'mid': (1.9, 5.0), 'thick': (2.1, 6.0)}
    # 字号:(基准 font.size, label, title, tick) —— 全局 rcParams,必生效
    _font = {'small': (9, 10, 11, 8), 'medium': (11, 12, 13, 10), 'large': (13, 14, 16, 12)}
    _bg = {'white': 'white', 'graytint': '#F7F8FA'}
    # 缺失/非法档位回落到第一档（与 _read_style_custom_marker 的补默认一致）
    f = _frame.get(spec.get('frame'), _frame['open'])
    g = _grid.get(spec.get('grid', 'none'), None) if spec.get('grid') != 'none' else None
    lw, ms = _lw.get(spec.get('lw'), _lw['mid'])
    fs = _font.get(spec.get('font'), _font['medium'])
    facecolor = _bg.get(spec.get('bg'), 'white')
    # legend 维显式选了就覆盖 frame 带的默认；没选则跟随 frame
    _leg = spec.get('legend')
    legend_frame = (_leg == 'framed') if _leg in ('framed', 'noframe') else f['legend_frame']
    return {
        'spines': f['spines'], 'tick_dir': f['tick_dir'], 'tick_tr': f['tick_tr'],
        'legend_frame': legend_frame, 'axis_color': f['axis_color'],
        'grid': g, 'patch_edge': 'white', 'lw': lw, 'ms': ms,
        'font_size': fs, 'facecolor': facecolor,   # ★ 新维(setup_style 用 .get 消费,预设路径无此键不受影响)
        '_name': f"custom({spec.get('frame','open')}/{spec.get('grid','none')}/{spec.get('lw','mid')}"
                 f"/{spec.get('font','medium')}/{spec.get('legend','-')}/{spec.get('bg','white')})",
    }


def setup_style(palette='auto', language=None, font_family=None):
    """Load project palette and layout; explicit palette arguments remain supported."""
    plt = _get_plt()
    import matplotlib
    language = vc.normalize_language(vc.load_config()['language'] if language is None else language)
    # Read family before seaborn resets rcParams; preserve a source's serif choice.
    family = font_family if font_family is not None else list(matplotlib.rcParams['font.family'])
    sns = _get_sns()
    _project_mode = palette == 'auto' or palette is None
    _custom_spec = _read_style_custom_marker() if _project_mode else None
    _knobs = (_knobs_from_custom(_custom_spec) if _custom_spec else
              dict(STYLE_FAMILIES[_read_style_marker()])) if _project_mode else None
    if isinstance(palette, list):
        colors = palette
    elif _project_mode:
        colors = vc.categorical_colors()
    elif palette in PALETTES:
        colors = list(PALETTES[palette])
    else:
        raise ValueError(f'Unknown palette: {palette}')

    # 更新全局 PALETTE 供其他函数使用
    global PALETTE, PALETTE_LIGHT, COLORS
    PALETTE[:] = colors
    PALETTE_LIGHT[:] = [_lighten(c, 0.4) for c in colors]
    COLORS['primary'] = colors[0]
    COLORS['secondary'] = colors[1] if len(colors) > 1 else colors[0]
    COLORS['accent'] = colors[2] if len(colors) > 2 else colors[0]
    # 语义颜色跟随配色方案
    COLORS['up'] = colors[2] if len(colors) > 2 else colors[0]       # 上升 = accent 色
    COLORS['down'] = colors[1] if len(colors) > 1 else colors[0]     # 下降 = secondary 色
    COLORS['highlight'] = colors[4] if len(colors) > 4 else colors[0]  # 高亮
    COLORS['bg_fill'] = _lighten(colors[0], 0.8)
    COLORS['bg_fill2'] = _lighten(colors[1] if len(colors)>1 else colors[0], 0.8)

    # 保持既有导出边界设置。
    matplotlib.rcParams['savefig.bbox'] = 'standard'
    matplotlib.rcParams['savefig.pad_inches'] = 0.1

    # 用 seaborn 主题（如果可用）
    if sns:
        sns.set_theme(style='ticks', font_scale=1.0, rc={
            'axes.edgecolor': '#333333',
            'axes.linewidth': 0.8,
        })
    if sns:
        sns.set_palette(colors)

    # One shared font policy for initialization and final export. Local fonts
    # are registered on demand; no platform-specific installation is attempted.
    selected_fonts = font_candidates(language, family)
    sans_fonts = font_candidates(language, 'sans-serif')
    serif_fonts = font_candidates(language, 'serif')

    matplotlib.rcParams.update({
        'font.size': 11,
        'font.family': selected_fonts,
        'font.sans-serif': sans_fonts,
        'font.serif': serif_fonts,
        'font.monospace': font_candidates(language, 'monospace'),
        'axes.unicode_minus': False,
        'axes.labelsize': 12,
        'axes.titlesize': 13,
        'axes.linewidth': 0.8,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'legend.frameon': False,
        'figure.dpi': 300,
        'savefig.dpi': 350,
        'pdf.fonttype': 42,  # Embed TrueType text with Unicode mappings.
        'ps.fonttype': 42,
        'savefig.bbox': 'standard',       # ★ 不用 'tight' — 否则 axes 外文字会撑爆 mediabox
        'savefig.pad_inches': 0.1,        # ★ 配合 standard，留窄边距
        'axes.grid': False,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.facecolor': 'white',
        'figure.facecolor': 'white',
        'text.usetex': False,
        'mathtext.fontset': 'stix',
        'lines.linewidth': 1.8,
        'lines.markersize': 6,
        'patch.edgecolor': 'white',       # 饼图/柱状图块之间白色分隔线
        'patch.linewidth': 1.0,
    })

    # 设置颜色循环 — 这是关键，防止 matplotlib 用默认丑蓝色
    matplotlib.rcParams['axes.prop_cycle'] = matplotlib.cycler(color=colors)

    # ★ 随机模式：按【成品风格族】整套应用版式（自洽、好看；显式控制刻度四面 = 消灭上右黑点）
    if _project_mode and _knobs:
        _f = _knobs
        _ac = _f['axis_color']
        _sp = _f['spines']
        _pe = _f['patch_edge']
        _grid = _f['grid']
        matplotlib.rcParams.update({
            'legend.frameon': bool(_f['legend_frame']),
            'lines.linewidth': _f['lw'],
            'lines.markersize': _f['ms'],
            # 边框：只显示 spines 里列出的面
            'axes.spines.left': ('left' in _sp),
            'axes.spines.bottom': ('bottom' in _sp),
            'axes.spines.top': ('top' in _sp),
            'axes.spines.right': ('right' in _sp),
            'axes.edgecolor': _ac,
            # 刻度：方向 + 是否上/右也画刻度（False=关掉上右刻度=去黑点）+ 颜色 + 长度
            'xtick.direction': _f['tick_dir'], 'ytick.direction': _f['tick_dir'],
            'xtick.top': _f['tick_tr'], 'ytick.right': _f['tick_tr'],
            'xtick.color': _ac, 'ytick.color': _ac,
            'xtick.major.size': 3.5 if _f['tick_dir'] == 'out' else 3,
            'ytick.major.size': 3.5 if _f['tick_dir'] == 'out' else 3,
            # 全局网格：仅 grid.axis=='both' 时全开；'y' 交给制图时按需（gax）。这里设默认样式
            'axes.grid': bool(_grid and _grid.get('axis') == 'both'),
            'grid.linestyle': (_grid or {}).get('ls', '--'),
            'grid.alpha': (_grid or {}).get('alpha', 0.3),
            'grid.color': (_grid or {}).get('color', '#DDDDDD'),
            # 描边：白/加粗白/无
            'patch.edgecolor': {'white': 'white', 'white_bold': 'white', 'none': 'none'}.get(_pe, 'white'),
            'patch.linewidth': {'white': 1.0, 'white_bold': 1.5, 'none': 0.0}.get(_pe, 1.0),
        })
        # ★ 高级自定义新维（字号/背景）——仅 custom 路径的 knobs 有这两键，用 .get 兜底，
        #   预设路径无此键时不覆盖上面设过的默认值（font.size=11 / facecolor=white）。
        _fsz = _f.get('font_size')
        if _fsz:
            _base, _lbl, _ttl, _tk = _fsz
            matplotlib.rcParams.update({
                'font.size': _base, 'axes.labelsize': _lbl, 'axes.titlesize': _ttl,
                'xtick.labelsize': _tk, 'ytick.labelsize': _tk, 'legend.fontsize': _tk,
            })
        _fc = _f.get('facecolor')
        if _fc:
            matplotlib.rcParams['axes.facecolor'] = _fc

    # ★ Hook plt.savefig — 即使不用 save_fig()，也能自动防遮挡
    # Preserve author layout: do not install automatic savefig mutation hooks.


def _has_3d_axes(fig):
    """检测 figure 是否含 3D 轴（Axes3D）。

    含 3D 轴时，所有针对 2D 子图的布局兜底（subplots_adjust / tight_layout /
    set_position 重排）都必须跳过：3D 曲面 + 窄 colorbar 的组合会命中"子图过窄"
    误判，被强行 tight_layout/subplots_adjust 挤塌成一条 colorbar（实测 3D 概率
    曲面图只剩右侧一根竖条）。matplotlib 官方亦声明 tight_layout 不支持 3D 轴。
    """
    try:
        for ax in fig.get_axes():
            if getattr(ax, 'name', '') == '3d' or hasattr(ax, 'get_zlim'):
                return True
    except Exception:
        pass
    return False


def _lighten(hex_color, amount=0.4):
    """将颜色变浅（用于填充区域）。amount=0 不变，amount=1 变白。"""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f'#{r:02x}{g:02x}{b:02x}'


# 初始化 PALETTE_LIGHT（必须在 _lighten 定义之后）
PALETTE_LIGHT = _Palette(_lighten(c, 0.4) for c in PALETTE)
COLORS["bg_fill"] = _lighten(PALETTE[0], 0.8)
COLORS["bg_fill2"] = _lighten(PALETTE[1], 0.8)


def _warn_if_wasted_margin(fig, output):
    """成品自检：保存前实测左边距，明显富余就打提示（不阻塞出图）。

    为什么需要：其他 9 道闸都是静态扫源码，而"左边距被撑爆"取决于 renderer 运行时
    实测，静态扫不出来 —— 历史上这个病就是这样潜伏下来的（对数轴幽灵刻度被当成
    越界，左边距一路顶到封顶 0.40，图上 40% 是白的）。

    判据不能拿"左距 > X%"一刀切：横向条形图配长中文 y 标签（特征重要性、方法对比）
    真的需要 25%+ 的左边距，那是合理的。所以拿【实测 y 标签宽度】当基准，
    只有左边距远超标签实际所需时才提示。
    """
    if _has_3d_axes(fig):
        return  # 3D 轴刻度在投影平面上，边距语义不同
    try:
        axes = [ax for ax in fig.get_axes()
                if ax.get_visible() and not ax.get_label().startswith('_')]
        if not axes:
            return
        fig_w_px = fig.get_size_inches()[0] * fig.dpi
        if fig_w_px <= 0:
            return
        left_px = min(ax.get_position().x0 for ax in axes) * fig_w_px
        if left_px <= 0:
            return
        renderer = fig.canvas.get_renderer()
        # y 刻度标签 + y 轴标题 实际占用的宽度
        need_px = 0.0
        for ax in axes:
            for t in _onscreen_tick_labels(ax, which='y'):
                if t.get_visible() and t.get_text().strip():
                    need_px = max(need_px, t.get_window_extent(renderer=renderer).width)
            lbl = ax.yaxis.label
            if lbl is not None and lbl.get_text().strip():
                need_px += lbl.get_window_extent(renderer=renderer).height
        need_px += 0.02 * fig_w_px  # 刻度线 + 呼吸余量
        # 只在"绝对富余够大"且"相对富余明显"时提示，避免误报刷屏
        if left_px - need_px > 0.06 * fig_w_px and left_px > need_px * 1.6:
            print(f"[plot_utils] WARNING {os.path.basename(str(output))} 左边距偏大: "
                  f"实测 {left_px / fig_w_px * 100:.1f}% 图宽，y 标签实际只需 "
                  f"{need_px / fig_w_px * 100:.1f}% —— 疑似空白浪费，检查坐标轴范围与刻度")
    except Exception:
        pass  # 自检永不影响出图


def _warn_if_data_clipped(fig, output):
    """成品自检：大量数据点落在轴范围外 → 几乎总是 xlim/ylim/zlim 写错。

    为什么必须运行时实测：静态扫源码看不出 `set_xlim(0, L)` 到底对不对 —— 那取决于
    数据坐标系的约定。实测起因是把主胞「边长 L=10000」当成了坐标上界，而数据其实以
    原点为中心（[-L/2, +L/2]），于是负坐标那一半（实测 46%~79% 的点）被静默裁到轴外，
    图上只剩挤在角落的一小撮，matplotlib 不报错、任何静态闸也扫不出来。

    阈值取 20%：合法的「裁掉几个离群点」通常远低于 5%，而坐标系写错必然接近 50%。
    """
    try:
        msgs = []
        for ax in fig.get_axes():
            if not ax.get_visible():
                continue
            is3d = getattr(ax, 'name', '') == '3d' or hasattr(ax, 'get_zlim')
            P = _data_points_in_data_space(ax, is3d)
            if P is None or P.shape[0] < 4:
                continue
            # 大数据集抽样：判「是否 >20% 的点落在轴外」不需要全量 —— 5 万样本的统计
            # 误差 <0.4%，而 90 万点全量实测要 1.74s，白加在每次 save_fig 上。
            # 固定 seed 保证同一张图重复跑结论一致（不引入随机抖动）。
            if P.shape[0] > 50000:
                P = P[np.random.default_rng(0).choice(P.shape[0], 50000, replace=False)]
            axinfo = [(ax.get_xlim(), ax.get_xscale()), (ax.get_ylim(), ax.get_yscale())]
            if is3d:
                axinfo.append((ax.get_zlim(),
                               getattr(ax, 'get_zscale', lambda: 'linear')()))
            for k, ((lo, hi), scale) in enumerate(axinfo):
                if k >= P.shape[1]:
                    break
                v = P[:, k]
                v = v[np.isfinite(v)]
                if scale == 'log':
                    v = v[v > 0]      # log 轴上非正值 matplotlib 本就不画，不算被裁
                if v.size < 4:
                    continue
                lo, hi = min(lo, hi), max(lo, hi)
                n_out = int(((v < lo) | (v > hi)).sum())
                if n_out / v.size > 0.20:
                    msgs.append(
                        f"{'xyz'[k]} 轴: {n_out}/{v.size} ({n_out / v.size:.0%}) 个点落在 "
                        f"[{lo:.4g}, {hi:.4g}] 之外，数据实际范围 [{v.min():.4g}, {v.max():.4g}]")
        if msgs:
            print(f"[plot_utils] ⛔ {os.path.basename(str(output))} 有数据被坐标轴裁掉：")
            for m in msgs[:6]:
                print(f"    {m}")
            print("    这几乎总是 set_xlim/set_ylim/set_zlim 写错。最常见的坑：把「边长/总长 L」")
            print("    当成坐标上界写了 (0, L)，而数据坐标系以原点为中心，应为 (-L/2, +L/2)。")
            print("    先打印数据真实 min/max 再定轴范围；别用 figsize / view_init 掩盖 ——")
            print("    被裁的点是真的没画出来。（若确为有意放大局部 inset，可忽略本条）")
    except Exception:
        pass  # 自检永不影响出图


def _flatten_segments(segs):
    """把 LineCollection / Line3DCollection 的 segments 展平成 (N, 2|3)。

    段等长（绝大多数情况，每段 2 点）时 np.asarray 能直接生成 3 维数组，
    实测 20 万段 39ms；退回 Python 列表推导要 133ms。段长不齐时 asarray 抛
    ValueError（numpy 不再允许 ragged），故用 except 兜住走慢路径。
    """
    try:
        a = np.asarray(segs, dtype=float)
        if a.ndim == 3:
            return a.reshape(-1, a.shape[-1])
    except Exception:
        pass
    return np.asarray([p for seg in segs for p in seg], dtype=float)


def _data_points_in_data_space(ax, is3d):
    """收集该 axes 上确实处于「数据坐标系」的点，返回 (N,2) / (N,3) 或 None。

    精确区分 transform 是本函数的全部难点，判据都是实测出来的：
      · Line2D      → get_transform() is ax.transData（axhline/axvline 是 blended，自动排除）
      · scatter     → offsets 走 get_offset_transform()，**不是** get_transform()
                      （实测 2D scatter 的 get_transform() 返回 IdentityTransform，
                        照搬 Line2D 的判据会把所有散点图漏掉）
      · LineCollection/vlines → get_segments() + get_transform() is ax.transData
      · 3D          → get_segments() 在投影前返回空，必须用私有 _segments3d / _offsets3d；
                      3D 的 transData 是投影后的，故 3D 分支不做 transform 判据
    故意跳过 fill_between(PolyCollection) 与 plot_surface(Poly3DCollection)：
    它们的顶点常含 baseline / 示意平面，位置由代码指定而非数据，算进去会误报。
    """
    pts = []
    for l in getattr(ax, 'lines', []):
        try:
            if is3d and hasattr(l, 'get_data_3d'):
                pts.append(np.asarray(l.get_data_3d(), dtype=float).T)
            elif not is3d and l.get_transform() is ax.transData:
                pts.append(np.asarray(l.get_xydata(), dtype=float))
        except Exception:
            pass
    for c in getattr(ax, 'collections', []):
        try:
            if is3d:
                s3 = getattr(c, '_segments3d', None)
                if s3 is not None and len(s3):
                    pts.append(_flatten_segments(s3))
                    continue
                o3 = getattr(c, '_offsets3d', None)
                if o3 is not None and len(o3) == 3:
                    pts.append(np.asarray(o3, dtype=float).T)
                continue
            hit = False
            if hasattr(c, 'get_offsets') and hasattr(c, 'get_offset_transform'):
                if c.get_offset_transform() is ax.transData:
                    o = np.asarray(c.get_offsets(), dtype=float)
                    if o.size:
                        pts.append(o)
                        hit = True
            if not hit and hasattr(c, 'get_segments') and c.get_transform() is ax.transData:
                sg = c.get_segments()
                if len(sg):
                    pts.append(_flatten_segments(sg))
        except Exception:
            pass
    try:
        pts = [p.reshape(-1, p.shape[-1]) for p in pts if getattr(p, 'size', 0)]
        want = 3 if is3d else 2
        pts = [p for p in pts if p.shape[-1] == want]
        return np.vstack(pts) if pts else None
    except Exception:
        return None


_ENGLISH_LABELS_CACHE = (None, None, {})


def _merged_english_labels(cfg=None):
    """Load english-labels.json beside plot_utils.py and merge config english_labels."""
    global _ENGLISH_LABELS_CACHE
    import json
    from pathlib import Path

    dict_path = Path(__file__).resolve().with_name('english-labels.json')
    base = {}
    if dict_path.is_file():
        mtime = dict_path.stat().st_mtime_ns
        if _ENGLISH_LABELS_CACHE[0] == str(dict_path) and _ENGLISH_LABELS_CACHE[1] == mtime:
            base = dict(_ENGLISH_LABELS_CACHE[2])
        else:
            loaded = json.loads(dict_path.read_text(encoding='utf-8'))
            if isinstance(loaded, dict):
                _ENGLISH_LABELS_CACHE = (str(dict_path), mtime, loaded)
                base = dict(loaded)
    if cfg is None:
        cfg = vc.load_config()
    extra = cfg.get('english_labels') if isinstance(cfg, dict) else None
    if isinstance(extra, dict):
        base.update(extra)
    return base


def _normalize_formats(formats, supported, caller):
    if isinstance(formats, str):
        items = [formats]
    else:
        items = list(formats)
    if not items:
        raise ValueError(f"{caller}: formats cannot be empty")
    normalized = []
    for item in items:
        fmt = str(item).strip().lstrip('.').lower()
        if not fmt or fmt not in supported:
            raise ValueError(f"{caller}: unsupported format {item!r}")
        if fmt not in normalized:
            normalized.append(fmt)
    return normalized


def _save(fig, output, formats=None):
    """Save without changing author layout, labels, axes, or canvas size."""
    # ★ 空 / 仅空白 路径直接拒绝（避免兜底成隐藏文件 ".pdf"）
    if not output or not str(output).strip():
        raise ValueError("save_fig: output path is empty")
    output = str(output)  # 容 pathlib.Path
    os.makedirs(os.path.dirname(output) if os.path.dirname(output) else '.', exist_ok=True)
    # ★ 扩展名兜底：matplotlib.savefig 拿到未知 format（如 'fig_lollipop'）会 raise ValueError。
    # 历史配方里有大量 save_fig(fig, 'figures/fig_xxx') 不带扩展名的写法 —— 自动追加 .pdf（论文场景首选矢量格式）。
    _SUPPORTED_FMTS = ('pdf', 'png', 'svg', 'jpg', 'jpeg', 'eps', 'ps', 'tif', 'tiff', 'webp')
    _basename = os.path.basename(output)
    _maybe_ext = _basename.rsplit('.', 1)[-1].lower() if '.' in _basename else ''
    if _maybe_ext in _SUPPORTED_FMTS:
        _ext = _maybe_ext
        _stem = output[:-len(_ext) - 1]
    else:
        # 无扩展名 / 不是图像格式（如 'fig.v2'）→ 追加 .pdf
        _ext = 'pdf'
        _stem = output
        output = output + '.pdf'
    _req_fmts = _normalize_formats(formats, _SUPPORTED_FMTS, 'save_fig') if formats is not None else None
    _cfg = vc.load_config()
    _lang = vc.normalize_language(_cfg.get('language', 'zh'))
    if _lang == 'en' and not getattr(fig, '_vivid_localized_en', False):
        localize_figure(fig, language='en', labels=_merged_english_labels(_cfg))
        fig._vivid_localized_en = True
    apply_figure_fonts(fig, _lang)
    # ★ 成品自检：静态闸扫不出的"边距被撑爆"，在这里实测拦一道（只提示，不阻塞）
    _warn_if_wasted_margin(fig, output)
    # ★ 成品自检：数据被轴范围裁掉（坐标系约定写错，静态扫不出来），同样实测拦一道
    _warn_if_data_clipped(fig, output)
    if _req_fmts is None:
        _save_kwargs = {'format': _ext, 'pad_inches': 0.15, 'bbox_inches': None}
        if _ext in ('png', 'jpg', 'jpeg'):
            _save_kwargs['dpi'] = 350  # 防中文标签糊（与 docx_export PDF→PNG 兜底链路一致）
        fig.savefig(output, **_save_kwargs)
        _get_plt().close(fig)
        print(f'Saved: {output}')
    else:
        targets = []
        for _fmt in _req_fmts:
            _target = f'{_stem}.{_fmt}'
            _save_kwargs = {'format': _fmt, 'pad_inches': 0.15, 'bbox_inches': None}
            if _fmt in ('png', 'jpg', 'jpeg'):
                _save_kwargs['dpi'] = 350
            fig.savefig(_target, **_save_kwargs)
            targets.append(_target)
        _get_plt().close(fig)
        for _target in targets:
            print(f'Saved: {_target}')


def save_plotly(fig, output, formats=None, scale=3):
    """Save a Plotly figure with project display language and font policy."""
    if not output or not str(output).strip():
        raise ValueError("save_plotly: output path is empty")
    output = str(output)
    os.makedirs(os.path.dirname(output) if os.path.dirname(output) else '.', exist_ok=True)
    _PLOTLY_FMTS = ('pdf', 'png', 'svg', 'html')
    _basename = os.path.basename(output)
    _maybe_ext = _basename.rsplit('.', 1)[-1].lower() if '.' in _basename else ''
    if _maybe_ext in _PLOTLY_FMTS:
        _ext = _maybe_ext
        _stem = output[:-len(_ext) - 1]
    else:
        _ext = 'pdf'
        _stem = output
        output = output + '.pdf'
    if formats is None:
        _targets = [(output, _ext)]
    else:
        _req_fmts = _normalize_formats(formats, _PLOTLY_FMTS, 'save_plotly')
        _targets = [(f'{_stem}.{_fmt}', _fmt) for _fmt in _req_fmts]
    cfg = vc.load_config()
    lang = vc.normalize_language(cfg.get('language', 'zh'))
    if lang == 'en':
        if not getattr(fig, '_vivid_localized_en', False):
            try:
                from .figure_language import localize_plotly
            except ImportError:
                from figure_language import localize_plotly
            localize_plotly(fig, language='en', labels=_merged_english_labels(cfg))
            fig._vivid_localized_en = True
        else:
            apply_figure_fonts(fig, 'en')
    else:
        apply_figure_fonts(fig, lang)
    for target, ext in _targets:
        if ext == 'html':
            fig.write_html(target)
        else:
            fig.write_image(target, scale=scale if ext == 'png' else 1)
        print(f'Saved: {target}')


def _onscreen_tick_labels(ax, which='both'):
    """返回该 axes 上真正落在轴范围内的主刻度标签（Text 对象列表）。

    which: 'both' | 'x' | 'y'，只取对应轴的刻度。

    matplotlib 会为超出 xlim/ylim 的刻度保留 Text 对象——对数轴尤其常见：
    xlim=[10, 2700] 时 10^0（x=1）的刻度对象依然存在，只是不绘制。这种
    "幽灵刻度"的 window_extent 算出来远在画布左侧（实测可达 -457 px），
    若拿去做"标签被画布切掉"的判定，会误判成越界，进而把左边距一路加大
    到封顶值，图上就出现大片空白。

    过滤办法：在轴自身的变换空间里比较（log 轴即 log 空间），只保留位置落在
    [lo, hi] ±0.5% 跨度内的刻度。测不出来时保守保留，维持原有行为。
    """
    # ★ 3D 轴：刻度标签落在投影平面上，get_position() 不是数据坐标，与 xlim/ylim
    #   比对无意义（实测越界量会算出上千万像素的垃圾值）。调用方本就豁免 3D，
    #   这里再兜一层，防止将来别处误用。
    try:
        if getattr(ax, 'name', '') == '3d' or hasattr(ax, 'get_zlim'):
            return []
    except Exception:
        pass

    out = []
    pairs = ((ax.xaxis, True), (ax.yaxis, False))
    if which == 'x':
        pairs = pairs[:1]
    elif which == 'y':
        pairs = pairs[1:]
    for axis, is_x in pairs:
        try:
            labels = [t for t in axis.get_ticklabels() if t.get_text()]
        except Exception:
            continue
        if not labels:
            continue
        # 轴的 scale 变换（log/linear/symlog…），把范围判定统一到线性空间
        bounds = None
        try:
            tr = axis.get_transform()
            lo, hi = ax.get_xlim() if is_x else ax.get_ylim()
            a, b = (float(v) for v in np.asarray(tr.transform([lo, hi])).ravel()[:2])
            if b < a:
                a, b = b, a
            span = b - a
            if np.isfinite(a) and np.isfinite(b) and span > 0:
                tol = 0.005 * span
                bounds = (a - tol, b + tol)
        except Exception:
            bounds = None
        if bounds is None:
            out.extend(labels)  # 拿不到范围就不过滤，保持旧行为
            continue
        for t in labels:
            try:
                pos = t.get_position()
                loc = float(pos[0] if is_x else pos[1])
                v = float(np.asarray(tr.transform([loc])).ravel()[0])
                if not np.isfinite(v):
                    continue  # 非法位置（如 log 轴上的 ≤0）必然不显示
                if bounds[0] <= v <= bounds[1]:
                    out.append(t)
            except Exception:
                out.append(t)  # 测量失败时保守保留
    return out


def auto_truncate_yticklabels(ax, max_chars=20, suffix='…'):
    """公开 API：主动截断超长 y tick labels（配方代码可调用，防止 y 轴遮挡）。
    
    用法：
        ax.set_yticklabels(long_method_names, fontsize=10)
        auto_truncate_yticklabels(ax, max_chars=18)  # 超过 18 字符的截断
    
    适用场景：聚类热力图、SHAP 图、特征重要性图 — 这些图 y 轴标签是变量名/方法名，
    遇到长字符串（"average_silhouette_coefficient_2024" 等）会溢出 figure 左边界。
    
    注意：matplotlib 在重绘时可能用 formatter 覆盖单个 Text，所以这里整批 set_yticklabels。
    """
    labels = ax.get_yticklabels()
    if not labels:
        return
    fontsize = labels[0].get_fontsize() if labels else None
    new_texts = []
    for lbl in labels:
        txt = lbl.get_text()
        if len(txt) > max_chars:
            new_texts.append(txt[: max_chars - 1] + suffix)
        else:
            new_texts.append(txt)
    # 用 set_yticklabels 整批替换（同时锁定原 tick 位置避免 matplotlib warning）
    try:
        ax.set_yticks(ax.get_yticks())
        if fontsize is not None:
            ax.set_yticklabels(new_texts, fontsize=fontsize)
        else:
            ax.set_yticklabels(new_texts)
    except Exception:
        # 兜底：单个 set_text
        for lbl, new_txt in zip(labels, new_texts):
            lbl.set_text(new_txt)


# 公开别名，供外部脚本调用
save_fig = _save


# ============================================================
# 标签防遮挡工具
# ============================================================

def _ensure_adjustText():
    """确保 adjustText 库可用，不可用时自动安装。"""
    try:
        from adjustText import adjust_text
        return adjust_text
    except ImportError:
        try:
            import subprocess
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', 'adjustText', '-q'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            from adjustText import adjust_text
            return adjust_text
        except Exception:
            return None


def smart_labels(ax, xs, ys, texts, colors=None, fontsize=9, fontweight='normal',
                 offset=(8, 0), fmt=None, ha='left', va='center',
                 force_points=0.3, force_text=0.5, avoid_self=True,
                 bbox=None, arrowprops=None, max_labels=50):
    """智能标签标注 — 自动检测并推开重叠标签。

    优先使用 adjustText 库做物理模拟推开；如果不可用，退化为
    基于数据间距的简易偏移策略。

    Args:
        ax: matplotlib Axes 对象
        xs: 标签锚点 x 坐标列表
        ys: 标签锚点 y 坐标列表
        texts: 标签文本列表
        colors: 每个标签的颜色（None 则统一用深灰）
        fontsize: 字号
        fontweight: 字重（'bold' / 'normal'）
        offset: (dx, dy) 像素偏移，adjustText 模式下作为初始偏移
        fmt: 格式化字符串，如 '{:.3f}'，传入时 texts 应为数值列表
        ha/va: 水平/垂直对齐
        force_points: adjustText 的点斥力
        force_text: adjustText 的文本斥力
        avoid_self: 是否避免标签之间重叠
        bbox: 标签背景框样式 dict（如 dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7)）
        arrowprops: 箭头样式 dict（如 dict(arrowstyle='->', color='gray', lw=0.5)）
        max_labels: 超过此数量时跳过标注（数据太密集标注无意义）

    Returns:
        list of Text 对象

    用法示例::

        # 棒棒糖图标注
        smart_labels(ax, scores, y_pos, [f'{s:.3f}' for s in scores],
                     colors=[PALETTE[0]]*len(scores), fontweight='bold')

        # 散点图标注（带箭头）
        smart_labels(ax, x_outliers, y_outliers, gene_names,
                     arrowprops=dict(arrowstyle='->', color='gray', lw=0.5))
    """
    if len(xs) > max_labels:
        return []

    plt = _get_plt()
    text_objs = []

    # 格式化文本
    if fmt is not None:
        display_texts = [fmt.format(t) for t in texts]
    else:
        display_texts = [str(t) for t in texts]

    default_color = '#333333'

    # 创建 Text 对象
    for i, (x, y, txt) in enumerate(zip(xs, ys, display_texts)):
        c = colors[i] if colors and i < len(colors) else default_color
        fw = fontweight if isinstance(fontweight, str) else (
            fontweight[i] if i < len(fontweight) else 'normal')
        t = ax.text(x, y, txt, fontsize=fontsize, fontweight=fw,
                    color=c, ha=ha, va=va,
                    bbox=bbox if bbox else None)
        text_objs.append(t)

    # 尝试用 adjustText 自动推开
    adjust_text = _ensure_adjustText()
    if adjust_text and avoid_self and len(text_objs) > 1:
        try:
            arrow_kw = arrowprops or dict(arrowstyle='-', color='#cccccc', lw=0.3)
            adjust_text(text_objs, ax=ax,
                        force_points=force_points,
                        force_text=force_text,
                        expand_points=(1.5, 1.5),
                        arrowprops=arrow_kw)
        except Exception:
            # adjustText 失败时退化为手动偏移
            _fallback_offset(ax, text_objs, xs, ys, offset)
    else:
        # 没有 adjustText，用简易偏移
        _fallback_offset(ax, text_objs, xs, ys, offset)

    return text_objs


def _fallback_offset(ax, text_objs, xs, ys, offset):
    """简易防遮挡：根据数据间距计算偏移方向，密集区域交替上下偏移。"""
    if not text_objs:
        return

    fig = ax.get_figure()
    renderer = fig.canvas.get_renderer() if hasattr(fig.canvas, 'get_renderer') else None

    # 获取数据坐标范围
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    x_range = xlim[1] - xlim[0] if xlim[1] != xlim[0] else 1
    y_range = ylim[1] - ylim[0] if ylim[1] != ylim[0] else 1

    # 估算标签高度（数据坐标）
    label_height = y_range * 0.035  # 约 3.5% 的 y 轴范围

    # 按 y 坐标排序，检测相邻标签是否过近
    indices = list(range(len(text_objs)))
    indices.sort(key=lambda i: ys[i])

    for k in range(len(indices)):
        i = indices[k]
        # 基础偏移
        dx_data = offset[0] * x_range / 500  # 像素偏移转数据坐标（近似）
        dy_data = offset[1] * y_range / 500

        # 检查与前一个标签是否过近
        if k > 0:
            j = indices[k - 1]
            gap = abs(ys[i] - ys[j])
            if gap < label_height * 1.5:
                # 交替上下偏移
                direction = 1 if k % 2 == 0 else -1
                dy_data += direction * label_height * 0.8

        text_objs[i].set_position((xs[i] + dx_data, ys[i] + dy_data))


def check_legend_overlap(ax, preferred_locs=None):
    """自动选择不遮挡数据的图例位置。

    检测数据分布的稀疏区域，把图例放在最空的角落。

    Args:
        ax: matplotlib Axes 对象
        preferred_locs: 优先尝试的位置列表，默认 ['upper right', 'upper left',
                        'lower right', 'lower left', 'center right']

    Returns:
        最佳位置字符串（可直接传给 ax.legend(loc=...)）
    """
    if preferred_locs is None:
        preferred_locs = ['upper right', 'upper left', 'lower right',
                          'lower left', 'center right', 'center left']

    # 收集所有数据点
    all_x, all_y = [], []
    for line in ax.get_lines():
        xd, yd = line.get_xdata(), line.get_ydata()
        if len(xd) > 0:
            all_x.extend(xd)
            all_y.extend(yd)
    for coll in ax.collections:
        offsets = coll.get_offsets()
        if len(offsets) > 0:
            all_x.extend(offsets[:, 0])
            all_y.extend(offsets[:, 1])

    if not all_x:
        return preferred_locs[0]

    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    xmid = (xlim[0] + xlim[1]) / 2
    ymid = (ylim[0] + ylim[1]) / 2

    # 统计每个象限的数据点密度
    quadrant_counts = {
        'upper right': 0, 'upper left': 0,
        'lower right': 0, 'lower left': 0,
        'center right': 0, 'center left': 0,
    }
    for x, y in zip(all_x, all_y):
        if y >= ymid:
            if x >= xmid:
                quadrant_counts['upper right'] += 1
            else:
                quadrant_counts['upper left'] += 1
        else:
            if x >= xmid:
                quadrant_counts['lower right'] += 1
            else:
                quadrant_counts['lower left'] += 1
        # center 区域
        if abs(y - ymid) < (ylim[1] - ylim[0]) * 0.25:
            if x >= xmid:
                quadrant_counts['center right'] += 1
            else:
                quadrant_counts['center left'] += 1

    # 在 preferred_locs 中选密度最低的
    best_loc = min(preferred_locs, key=lambda loc: quadrant_counts.get(loc, 999))
    return best_loc


def auto_legend(ax, **kwargs):
    """智能图例：自动选择不遮挡数据的位置。

    用法：用 auto_legend(ax) 替代 ax.legend()

    Args:
        ax: matplotlib Axes 对象
        **kwargs: 传给 ax.legend() 的其他参数
    """
    loc = check_legend_overlap(ax)
    # ⛔ 默认去框：实证对比 94 张真实竞赛图，带灰框图例是"显土"的主要来源之一
    #    （高分图去框率 37% vs 平庸图 0%）。收紧 labelspacing/handlelength 让图例更紧凑。
    #    调用方仍可用 auto_legend(ax, frameon=True) 覆盖。
    defaults = dict(frameon=False, fontsize=9, labelspacing=0.35, handlelength=1.6,
                    borderpad=0.3, fancybox=False, shadow=False)
    defaults.update(kwargs)
    defaults['loc'] = loc
    return ax.legend(**defaults)


# ============================================================
# 图表函数
# ============================================================

def heatmap(data, labels=None, output='figures/fig_heatmap.pdf', title=None,
            annot=True, fmt='.2f', cmap=None, figsize=(8, 6)):
    """相关性热力图（带数值标注）。
    
    Args:
        data: 2D array 或 DataFrame（相关系数矩阵）
        labels: 行列标签
        output: 输出路径
        annot: 是否标注数值
        fmt: 数值格式
    """
    plt = _get_plt()
    sns = _get_sns()
    setup_style()
    try:
        from .palette_maps import palette_cmap, contrast_text
    except ImportError:
        from palette_maps import palette_cmap, contrast_text
    if cmap is None:
        cmap = palette_cmap('diverging')
    fig, ax = plt.subplots(1, 1, figsize=figsize)

    if sns:
        mask = np.triu(np.ones_like(data, dtype=bool), k=1)
        hm = sns.heatmap(data, mask=mask, annot=annot, fmt=fmt, cmap=cmap,
                    center=0, square=True, linewidths=0.5,
                    xticklabels=labels, yticklabels=labels, ax=ax,
                    cbar_kws={'shrink': 0.8})
        # 文字颜色自适应：深色格子用白字，浅色格子用黑字
        if annot and hasattr(hm, 'texts'):
            from matplotlib.colors import Normalize
            flat = np.array(data).flatten()
            flat = flat[~np.isnan(flat)]
            if len(flat) > 0:
                norm = Normalize(vmin=flat.min(), vmax=flat.max())
                for text in hm.texts:
                    try:
                        val = float(text.get_text())
                        mesh = hm.collections[0]
                        text.set_color(contrast_text(mesh.cmap(mesh.norm(val))))
                    except (ValueError, TypeError):
                        pass
    else:
        im = ax.imshow(data, cmap=cmap, aspect='auto', vmin=-1, vmax=1)
        fig.colorbar(im, ax=ax, shrink=0.8)
        if annot:
            for i in range(data.shape[0]):
                for j in range(data.shape[1]):
                    if j <= i:
                        val = data[i, j]
                        color = contrast_text(im.cmap(im.norm(val)))
                        ax.text(j, i, f'{val:{fmt}}', ha='center', va='center', fontsize=8, color=color)
        if labels is not None:
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels)

    _save(fig, output)
