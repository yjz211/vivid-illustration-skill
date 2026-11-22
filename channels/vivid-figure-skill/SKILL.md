---
name: vivid-figure-skill
description: 从真实数据规划、生成、修改和检查科研与数学建模数据图；使用145个配方和3套完整组合模板，保留模板设计并适配统计含义、语言和配色。
---

# Vivid Figure Skill · 数据图

处理数值比较、分布、关系、时序预测、统计检验、优化结果及真实空间数据的图件。三个阶段是一次任务内的连续步骤，无需额外模型调用。

`<SKILL>` 指本文件向上两级的包根目录（`../../`），不是 `channels/vivid-figure-skill/`；`<RES>` 为 `<SKILL>/original/resources`。`_utils/`、`figures/` 和 `.vivid/` 位于当前任务工作区 `<WORKSPACE>`，直接复用根目录资源，不复制文件到子通道。

## 选择、适配、检查

1. **选择模板**：首次选图读取 [数据与模板选择](../../figure-selection.md)，运行 `search_figure.py` 检索候选，查看 [预览图](../../catalog/previews/) 并阅读所选卡片（`catalog/<card_path>`）。用户已指定模板时直接定位卡片与预览；修图或换色沿用现有有效源码，跳过重新选择。
2. **源码适配**：读取 [源码底稿与保真](../../template-fidelity.md) 与所选卡片，用 `_utils/get_recipe.py` 将完整源码生成工作脚本并记录来源底稿，在该文件上原位替换真实数据、变量绑定与标签，按需局部调整画布或间距。保留模板的字号层级、图层、填充、渐变、透明度、描边、标记与短注释框，不为适配数据整段重写绘图主体。
3. **自检与看图**：运行脚本并确认其退出码及本图目标文件后，执行 `python _utils/figure_check.py`，再打开实际导出图件核对模板特征、统计口径、文字、图例与边界裁切。多轮修复上限与论文级页面复核见 [检查与修复](../../original/review-policy.md)。

## 运行与命令速查

首次运行确认 Python 3.10+ 及 [依赖](../../requirements.txt)，初始化工作区（已有 `.vivid/runtime.json` 直接复用；多渲染器环境详见 [执行环境](../../host-adapter.md)）：

```bash
python "<RES>/scripts/resolve_runtime.py"
python "<RES>/scripts/bootstrap.py" --workspace "<WORKSPACE>" --profile modeling-competition --capability paper-figure
```

单图标准流程（检索候选 → 准备工作脚本 → 运行导出 → 质量与底稿检查）：

```bash
python "<SKILL>/scripts/search_figure.py" "<表达目的或数据结构>" --limit 8
python _utils/get_recipe.py --id empirical.prediction_ci --script figures/gen_fig_forecast.py
python -m figures.gen_fig_forecast
python _utils/figure_check.py
```

逐项核对当前脚本自身的退出状态与预期输出文件，不以其他图存在代替本图成功。

## 三套完整组合模板

- `template.sem_violin_pearson`：[小提琴＋Pearson](../../templates/sem-violin-pearson/TEMPLATE.md)，保留整套原版默认样式与数据接口。
- `template.shap_dependence`：[SHAP组合](../../templates/shap-composites/TEMPLATE.md)的特征重要性与响应模式（`--mode dependence`）。
- `template.shap_contribution`：同一 [SHAP组合](../../templates/shap-composites/TEMPLATE.md)的变量及类别贡献模式（`--mode contribution`）。

三套组合均使用各自完整源码、输入口径与原 CLI，不拆成普通配方重拼，也不当作无参数脚本运行；SHAP 模式须输入真实特征值及对应 SHAP 值。准备已登记工作副本的方法见 [源码底稿与保真](../../template-fidelity.md)。

## 数据与显示默认值

- **真实数据**：绘图数值来自用户输入、模型结果或可追溯计算；明确观测单位、分组/配对、量纲单位、缺失处理及 SD/SE/CI 含义。全部替换演示数据和统计量，不补造样本、阈值、显著性、不确定性或三维结构；缺少数据支撑的条件图层直接移除并简述原因。
- **图内语言**：默认中文（`language: zh`），用户要求英文时设 `language: en`（`python _utils/vivid_config.py set language en`）。同一份源码通过 `save_fig` / `save_plotly` 结合 `english-labels.json` 与 `.vivid/config.json` 的 `english_labels` 自动切换标题、坐标轴、图例、色条与数值标注语言，保留数据键、专业缩写、单位与公式。
- **默认字体**：无衬线数据图的英文与数字优先 `Arial`、中文优先 `MiSans`（缺字按系统无衬线与中文字体回退）；保留模板明确设计的衬线字体、用户指定样式及字号层级。`setup_style()`、`save_fig`、`save_plotly` 自动应用字体策略。
- **默认配色**：默认橄榄杏棕（`olive-apricot`），工作区已有配置或用户指定颜色优先，无需额外确认环节。切换预设、自定义 HEX 色列及连续/发散色阶规则按需查阅 [配色选择](../../color-selection.md)。

## 任务边界与按需引用

- 完整论文或整题图集先回到 [根入口](../../SKILL.md)，读取 [上游规划](../../original/upstream-planning.md)、[绘图入口](../../original/resources/ENTRYPOINT.md) 与 [数据图执行](../../original/resources/references/paper-figure.md)，按 `FIGURE_PLAN.json` / `FIGURE_MANIFEST` 执行其中 `DATA` 项并对账；单图及限定小批数据图不启动整题规划。
- 请求表达模型/系统架构或非数据精确结构时，由 [根入口](../../SKILL.md) 转入架构图或对应技术图通道；仅画数据图时不初始化其他渲染器。
- 进阶版面精调、防遮挡与局部统计技法按需查阅 [绘图知识索引](../../original/resources/assets/shared-scripts/figure_style_guide.md)。仅图件任务交付可复现脚本、输入来源与目标图件后结束，不自动生成论文或额外表格。
