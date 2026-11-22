# 数据与模板选择

用于首次选定数据图模板；用户已指定模板时直接定位对应卡片与预览，修图或换色沿用现有源码，不重复选图。以下路径相对于 `<SKILL>`。

## 1. 数据画像与表达目的

先结合用户要求、论文上下文与实际数据明确本图要回答的问题：主要比较对象、关注的关系或变化，以及需呈现的分布、波动、不确定性或空间结构。仅在缺失信息会实质改变统计含义时才向用户确认，不设固定问卷步骤。

不清楚字段规模与分布时，运行数据摘要工具：

```bash
python "<SKILL>/scripts/profile_figure_data.py" "<WORKSPACE>/data.csv"
python "<SKILL>/scripts/profile_figure_data.py" "<WORKSPACE>/data.xlsx" --sheet Sheet1 --columns method score seed --group method --output "<WORKSPACE>/data-profile.json"
```

脚本输出行数、类型、缺失、有限数值范围、分位数、类别及组内有效样本数。结合字段业务含义判断观测单位、变量角色、时间顺序、是否配对及 SD/SE/CI 来源；不单凭列名或重复值猜测语义，也不为套用模板补造样本、误差或显著性。

## 2. 候选检索与实图对照

使用轻量检索 CLI 在全部 145 个普通配方与 3 套完整组合模板中按表达目的、数据结构和图形特征查找候选：

```bash
python "<SKILL>/scripts/search_figure.py" "<表达目的或数据结构>" --limit 8
```

支持按 `--category`（如 `compare`、`distribution`、`relation`、`timeseries`、`spatial`、`3d`、`model`、`composition`）过滤或加 `--json` 输出。关键词未命中理想结构或需全局浏览时，读取 [精简目录](catalog/selection-index.jsonl) 或参考 [数据形态决策表](original/resources/assets/shared-scripts/figure_selection_reference.md)；不以配方 ID 前缀限定候选范围。

使用宿主看图工具查看候选在 [预览目录](catalog/previews/) 中的实图，并阅读对应 `catalog/<card_path>` 的保留重点与允许适配范围。比较几个结构有区分度的候选，核对当前数据能否支撑图层、视觉特点是否有助表达、画布篇幅是否合适（预览图自身配色不影响项目色板选择）。看图工具不可用时如实说明，依据卡片与代码选择，不声称已完成视觉比较。

## 3. 新颖单图、同轴融合与多面板原则

未指定模板时，在任务记录中先写一句本图要回答的问题，比较两种有真实数据支撑的表达方式，只生成信息收益更高、视觉层次更清晰的一种：

- **新颖单图与同轴融合**：新颖感来自信息组织而非鲜艳换色或堆砌子图。优先评估契合数据的新颖单图，或在同一套坐标轴内叠合互补图形编码的**同轴融合图**（如真实散点＋等高线/核密度填色、折线＋真实置信带＋关键样本、空间地形＋测线＋覆盖轮廓、同类别位置的小提琴＋箱线＋原始散点）。同轴各层须表达同一研究对象并共享坐标语义，用浅色填充、原色线条、白边标记与 `zorder` 建立前景/背景主次；不把不同量纲强塞同轴，不把双轴当作默认融合捷径，也不虚构拟合、区间或可行域。
- **多面板组合**：仅在不同视角确有互补信息、单坐标系不易清楚表达时采用（如空间图＋剖面、主图＋边缘分布或局部放大），并在记录中写明各面板贡献；无需为保留清晰单图辩护，也不设多面板或融合图配额。

## 4. 衔接完整源码适配

在现有计划或任务记录中记下所选模板 ID、预览路径与简短理由，转入 [源码底稿与保真](template-fidelity.md) 准备工作脚本：

- 145 个普通配方（含 `screenshot.*` 的 Matplotlib 与 Plotly 模板）统一通过 `_utils/get_recipe.py` 写入工作脚本（`advanced.cluster_heatmap` 的双向聚类变体可用 `--variant two_way` 提取并接入真实输入）。
- `template.sem_violin_pearson` 按 [专用说明](templates/sem-violin-pearson/TEMPLATE.md) 执行；`template.shap_dependence` 与 `template.shap_contribution` 按 [SHAP组合说明](templates/shap-composites/TEMPLATE.md) 及对应 CLI 模式执行。
- `catalog/sources/` 仅保存预览溯源记录，实际绘图统一用准备工具提取当前注册配方。
