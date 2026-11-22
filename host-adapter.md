# 执行环境与项目配置

`<SKILL>` 是包根目录，`<RES>` 是 `<SKILL>/original/resources`，`<WORKSPACE>` 是当前任务工作区。

## 1. 工作区初始化

使用同一个 Python 3.10+ 环境安装 [依赖](requirements.txt) 后执行：

```bash
python "<RES>/scripts/resolve_runtime.py"
python "<RES>/scripts/bootstrap.py" --workspace "<WORKSPACE>" --profile modeling-competition --capability paper-figure
```

完整多渲染器图集可将 `--capability` 设为 `all`（HTML 路线另复制 `_templates/`）。初始化向工作区注入 `_utils/` 并记录环境路径至 `.vivid/runtime.json`；重复运行保留用户修改过的文件并刷新已知工具副本。后续命令在工作区执行，优先使用 `.vivid/runtime.json` 解析出的 Python 与 Bash（Windows 下使用 Git Bash，避免误调 WSL 启动器；也可通过环境变量 `VIVID_PYTHON`、`VIVID_BASH` 显式指定）。

## 2. 项目配置文件（.vivid/）

- `.vivid/config.json`：项目设置，由 `_utils/vivid_config.py` 读写（支持从子目录向上定位工作区根）。包含 `palette` / `colors`（见 [配色选择](color-selection.md)）、`language`（默认 `zh`，英文设 `en`）、`english_labels`（原文到英文显示名映射字典）、`style`（默认 `clean_open`）、`style_custom`、`output_format`（`pdf`/`png`/`docx` 等）、`template`、`title`；更新时保留用户已有字段。
- `.vivid/runtime.json`：可执行文件路径与工具复制记录。
- `.vivid/template-sources/` 与 `.vivid/figure-plan-policy.json`：分别由源码准备工具与完整图集规划 CLI 维护。

## 3. 语言本地化与默认字体

图内语言跟随 `.vivid/config.json` 的 `language`，与对话界面语言独立。当 `language` 为 `"en"` 时，`save_fig`（Matplotlib）与 `save_plotly`（Plotly）在保存前自动合并内置 `english-labels.json` 与 `.vivid/config.json` 中的 `english_labels`，调用 `localize_figure` / `localize_plotly` 完成标题、坐标轴、图例、色条与数值标注翻译，再应用英文字体栈；`language` 为 `"zh"` 时保持原中文路径不变。

也可在保存前显式传入映射并保护特定数据实体名（映射不更改输入表头、数值或分组键；长英文确有挤压时仅局部调整换行、图例位置或必要边距）：

```python
from _utils.figure_language import localize_figure
localize_figure(fig, language="en", labels={"实验组": "Treatment"}, protected_texts=["Model-X"])
```

中英文数据图共用默认字体策略：普通无衬线图的英文与数字优先 `Arial`、中文优先 `MiSans`，缺失时按已安装的 Helvetica / Liberation Sans / Noto Sans 和思源黑体 / Noto Sans CJK / 微软雅黑回退；保留明确设计的 Times New Roman 等衬线风格、用户指定字体样式、数学符号及字号层级。建议安装 [MiSans 官方 TTF](https://hyperos.mi.com/font/zh/download/) 的 Regular、Semibold、Bold 以提供完整中文粗体字形（支持识别系统与当前用户 Fonts 目录，PDF 使用 TrueType 嵌入）。`setup_style()`、`save_fig`、`save_plotly` 自动应用该策略；直接调用 `fig.savefig()` 时，在最终布局前调用 `_utils.figure_language.apply_figure_fonts(fig, language="zh")`（英文传 `"en"`）。

## 4. 渲染工具 CLI

- **数据图**：Python（Matplotlib / Plotly）；保存源脚本、真实输入与导出图件。
- **SVG 架构资产**：`python "<SKILL>/scripts/render_architecture.py" fig.svg`（Chromium 输出 PNG/PDF）；原生可编辑 PPTX 用 `scripts/export_architecture_pptx.py`，依赖见 [架构运行环境](requirements-architecture.txt)，流程与 Office 验证边界见 [PPTX 导出](architecture/PPTX.md) 与 [共同验收](architecture/COMMON.md)。
- **Draw.io**：`python "<RES>/scripts/export_drawio.py" source.drawio --format pdf`；需桌面版 Draw.io，可用 `DRAWIO_PATH` 指定。
- **HTML**：`python "<RES>/scripts/render_html.py" source.html --format both`；使用本机 Chrome/Chromium 与 Playwright，可用 `CHROME_PATH` 指定，公式加 `--render-math`，几何检查加 `--geom-check`。
- **TikZ**：XeLaTeX 编译；PDF 预览使用 PyMuPDF 或 Poppler。
- **Mermaid**：`python "<RES>/scripts/render_mermaid.py" source.mmd`；需 Node.js 与 `mmdc`。
- **科学场景插图**：使用宿主或用户已配置的图像生成工具并保留完整构图提示词；缺少工具时如实说明，不用插图替代数据证据。

非 SVG 架构路线的审图轮次与范围见 [检查与修复](original/review-policy.md)；仅要求出图时在图件完成后停止。
