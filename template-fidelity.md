# 源码底稿与保真适配

用于选定模板后的绘制、修图与换色。直接在工具生成的工作脚本上修改，保留所选模板的具体实现与视觉层次，不凭印象重写同类型图。以下路径相对于 `<SKILL>`，`_utils/` 与 `.vivid/` 位于工作区。

## 1. 准备工作脚本与来源底稿

工作区初始化后，用提取工具写入可执行 Python 工作脚本，并在 `.vivid/template-sources/` 保存原始底稿与来源记录：

```bash
python _utils/get_recipe.py --id empirical.prediction_ci --script figures/gen_fig_forecast.py
```

全部 145 个普通配方（含 `screenshot.*` 的 Matplotlib 与 Plotly 模板）及 3 套完整组合模板均保存真实来源底稿，并通过 `save_fig` / `save_plotly` 跟随工作区色板与中英文设置（支持传入 `formats=('pdf', 'png')` 同步导出多格式）。读取生成的工作脚本及工具返回的卡片保留重点即可，无需重复打印全文。变体配方可用 `--list-variants --id advanced.cluster_heatmap` 查看并加 `--variant two_way` 提取。

已有完整图集计划时支持混合批量准备（普通配方填 `recipe:<id>`，完整组合填 `template.*` 原始 ID；`asset:VA-*` 走 SVG 架构工作流）：

```bash
python _utils/get_recipe.py --plan FIGURE_PLAN.json PAPER_PLAN.md --scripts-dir figures
```

同一模板用于多张独立图时，对每张图分别执行 `--id <ID> --script <本图脚本>`。三套完整组合也可单独准备已登记副本，并按对应 `TEMPLATE.md` 的原 CLI 参数运行：

```bash
python "<SKILL>/scripts/prepare_complete_template.py" --id template.shap_dependence --script figures/plot_shap.py --workspace .
```

重复运行准备命令会保留已登记文件的适配修改；遇到未登记同名文件或底稿不一致时先核对现有文件，必要时指定新路径生成。

## 2. 原位数据替换与尺寸预计算

- **原位编辑，保留绘图主体**：在生成的工作脚本上用局部编辑将演示数组与模拟指标全部替换为真实数据读取、清洗与计算，再更新坐标轴、统计区间与标签绑定。保留原模板的折线/柱体/分布层、填充、渐变、透明度、原色描边、标记、字号层级与已有短标注框；不为适配数据整段重写绘图主体，也不顺手统一 `alpha`、线宽或框样式。公共数据清洗可抽入辅助模块。
- **统计真实与条件图层**：置信带、显著性、参考阈值、训练/测试分界、可行域等须有真实数据依据；当前数据不支持某层时直接移除对应构件并在说明中简记原因，不临时编造数值填空。组数、站点或长标签增加时复用原结构合理扩展画布、面板或边距，避免漏数据或异量纲强行共轴。长方法口径与阅读说明写入图注或随图说明，不默认新增图内大段文本框。
- **中英文同源**：中英文共用同一份源码，直接更新显示文字或按 [执行环境配置](host-adapter.md) 配置 `language` 与 `english_labels`，不翻译底层数据列名或分组键；重点系列按显式索引或标识选择，不靠名称字符串匹配判断。
- **尺寸预计算**：设定或调整 `figsize` 前，代入实际交付宽度与高度限制核算 `上页字号 = 代码字号 × 引用宽 ÷ 原生宽`（线宽按同一受限缩放比折算），避免原生画布远大于显示宽度导致缩印后文字过小。未固定上页宽度时按实际展示场景核对可读性；多面板间距、共用色条与防遮挡示例按需查阅 [布局与可读性参考](original/resources/assets/shared-scripts/figure_layout_reference.md)。

## 3. 代码自检与实图核对

在工作区运行脚本（推荐 `python -m figures.gen_fig_forecast`）并确认目标产物生成后，执行跨平台质量与来源检查（POSIX 环境兼容 `bash _utils/figure_check.sh`）：

```bash
python _utils/figure_check.py
```

`figure_check.py` 检查语法、主题/色板规范与导出调用，并在存在 `.vivid/template-sources/` 时自动调用 `_utils/recipe_style_review.py` 生成 `.vivid/source-review.json` 底稿差异摘要（单图检查可运行 `python _utils/recipe_style_review.py --workspace . --candidate figures/gen_fig_forecast.py --summary`）。

静态比对列出色带叠加层数、刻度标签、注释框及绘图层变化，作为审图线索而非机械禁令；合理的统计与版面适配无需改回演示写法，但**静态零告警不等于视觉或数据合格**。须按 [检查与修复](original/review-policy.md) 实际打开成图对照原预览与卡片要点，核验关键图层、统计口径、文字可读性、图例与边界裁切。
