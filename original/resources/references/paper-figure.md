# 数据图执行

处理完整图集或工作流路由中的 `DATA/TABLE` 项；单图选型、源码保真与环境细节复用包根目录规范。工具在任务工作区 `<WORKSPACE>` 执行，`<RES>` 为 `<SKILL>/original/resources`。

## 初始化与恢复

首次运行 `python "<RES>/scripts/bootstrap.py" --workspace "<WORKSPACE>" --profile modeling-competition --capability paper-figure`，使用 `.vivid/runtime.json` 中的 Python/Bash 路径，并按 [执行环境](../../../host-adapter.md) 读取语言、输出格式与项目配色。已初始化环境直接复用；重复运行保留用户修改并刷新已知工具副本。恢复任务时核对现有输入、源码、输出与清单，仅补齐缺失项或修复有问题图件，不无故重画。

## 选型、适配与尺寸

- 模板检索与实图对照按 [数据图子 Skill](../../../channels/vivid-figure-skill/SKILL.md) 与 [数据与模板选择](../../../figure-selection.md) 执行；工作脚本落盘、真实数据原位替换与尺寸预计算（`上页字号 = 代码字号 × 引用宽 ÷ 原生宽`）遵循 [源码底稿与保真](../../../template-fidelity.md)。
- 项目颜色在 `setup_style()` 后从 `pu.PALETTE`、`pu.COLORS` 及 `palette_cmap` 读取，规则见 [配色选择](../../../color-selection.md)（唯一色值表为 `palettes.json`）。所有数值与统计区间须来自真实输入或计算，不补造阈值、显著性或不确定性。

## 运行与检查

每张数据图保存可重跑源脚本（公共数据处理可放入辅助模块），推荐在工作区执行 `python -m figures.gen_fig_name`。PNG 通常不低于 300 DPI，矢量交付以 PDF 为主。批量并行前先单进程完成工具与字体缓存初始化，并逐脚本独立核对退出码与预期输出文件。

出图后执行跨平台质量与底稿检查（POSIX 环境兼容 `bash _utils/figure_check.sh`）：

```bash
python _utils/figure_check.py
```

工具检查语法、样式/色板规范与导出调用，并自动运行 `_utils/recipe_style_review.py` 生成 `.vivid/source-review.json` 差异摘要（单图检查可传 `--candidate figures/gen_fig_name.py`）；完整组合模板遵循各自 `TEMPLATE.md` 的专用 CLI 与检查说明。随后按 [检查与修复](../../review-policy.md) 查看实际成图，静态零提示不替代视觉与数据核对。

## 完整图集对账与论文引用（仅相应任务加载）

- 全图集由 [绘图入口](../ENTRYPOINT.md) 与 [路由合同](router-contract.md) 分类，执行后逐项对账 `FIGURE_MANIFEST`（验证器为 `<RES>/scripts/validate_figure_manifest.py`），不截断清单，不用结构图替代缺失的数据结果。
- 若工作区存在 `facts.json` 与 `_utils/facts_audit.py`（或 `skills/shared-scripts/facts_audit.py`），按其 CLI 核对图标签、实体、单位与来源；不存在时不声称已审计。
- 涉及论文表格、图注与页面尺寸规范时，读取 [表格与图注](figure-tables-and-captions.md) 与 [版面门禁](paper-layout-gate.md)。仅图件任务交付输入来源、脚本与所要求的图件后结束，不生成论文或额外表格。
