# 数据图执行

仅处理当前要求的数据图；选择模板、源码适配和审图分别见包入口链接。工具执行位置是任务工作区；`<RES>` 为 skill 的 `original/resources`。

## 初始化与恢复

首次运行 `python "<RES>/scripts/bootstrap.py" --workspace "<WORKSPACE>" --profile modeling-competition --capability paper-figure`，按 `host-adapter.md` 配置语言、输出和项目配色。初始化已完成时复用环境；工具更新时重跑会刷新已知旧副本并保留用户改动。使用 `.vivid/runtime.json` 中的 Python/Bash 路径。

恢复时核对现有输入、源码、输出及任务清单。保留有效结果；补缺失项，修复有具体问题或用户要求改变的图，不无故重画。来源工具遇到已有适配会保留，未登记的同名文件需先核对，不能强制覆盖。

## 数据与适配

- 明确观测单位、配对/分组、单位、缺失与统计区间的含义。绘图数值来自输入或真实计算；演示随机数和演示统计量必须替换。不能补造阈值、显著性或不确定性来凑模板。
- 按 `template-fidelity.md` 将完整源码落盘，再在文件中改数据载入、计算、绑定、标签及必要布局。公共数据处理可放辅助模块；主绘图结构保留在对应底稿中。
- 数据需要额外组别、站点、不同单位或长标签时，可扩展画布、复用模板结构增加面板或调整图例，避免漏数据和混单位。密度/区间不适合当前样本时按统计含义适配，并保留能成立的信息层。
- 项目颜色通过 `setup_style()` 后的 `pu.PALETTE` / `pu.COLORS` 读取。完整用色摘要见 [配方用色](../../fragments/original-color-usage.md)；连续色阶跟随语义及原配方归一化。具体配色数值唯一维护在 `palettes.json`。
- 尺寸按 [预计算](../../fragments/original-size-preflight.md) 处理，保留模板字体/图层关系。用户未指定上页尺寸时以实际交付用途判断，不把论文示例宽度当全库常量。

## 运行与检查

每张交付图有可重跑的脚本，可共享数据处理。推荐在工作区执行 `python -m figures.gen_fig_name`，使 `_utils` 等工作区导入可用；无需改写模板开头来解决路径。输出按要求使用 PNG/PDF 等；PNG 通常300 DPI以上，保留实际可读性，矢量PDF不以DPI代表矢量质量。

绘图前或首次运行检查时执行：

```text
python _utils/recipe_style_review.py --workspace . --summary --output .vivid/source-review.json
```

`--candidate figures/gen_fig_name.py` 可仅检查修复的一张图。来源缺失/不匹配、语法或运行失败应修复；布局、注释、颜色与图层变化是需结合数据判断的提示。详细 diff 保存到 JSON，按需读取，无需逐条长篇自评。

执行脚本并核对该脚本自己的预期输出；退出0或别的图文件存在不能证明本图成功。批量并行时各自记录退出码和输出，先单进程初始化工具/字体缓存，避免并发写入。

`bash _utils/figure_check.sh` 集成已有工程检查与登记源码比较。完整组合模板遵循专用CLI及检查说明，通用检查中不适用于其实现的要求不能覆盖模板约定。

随后按 [检查与修复](../../review-policy.md) 查看实际图件，核对源码差异与卡片要点，必要时修复。未经查看不声称审图通过；静态工具没有提示也不代表数据、布局或视觉正确。

## 论文及完整图集（仅相应任务加载）

- 全图集由 [入口](../ENTRYPOINT.md) 和 [路由合同](router-contract.md) 分类；执行非空路由后按 FIGURE_MANIFEST 清点。验证器位于 `<RES>/scripts/validate_figure_manifest.py`，不假设它在 `_utils/`。
- FIGURE_MANIFEST 与已有计划共同确定数量、来源和输出；不截断清单后对账，不按关键词计数替代逐项核对。图型重复支持一致比较，没有固定次数配额。
- 若工作区有 `facts.json` 与 `_utils/facts_audit.py`（或 `skills/shared-scripts/facts_audit.py`），按其CLI核对图标签、实体、单位及来源；不存在时不声称已审计。
- 表格和论文引用读取 [表格与图注](figure-tables-and-captions.md)。仅图件任务不生成论文、LaTeX引用或额外表格。
- 场景与确定性结构图交给各自路由，不能用结构图替代缺失的数据结果，也不因数据图任务强制增加场景图。

交付输入来源、脚本与所要求的图件；简述必要适配和仍未解决的问题。工作文件集中保存在本次工作区。
