# 配色选择

七套预设色板及颜色顺序唯一维护于 [palettes.json](original/resources/assets/shared-scripts/palettes.json)，文档与脚本不另存颜色表。

可选预设：**橄榄杏棕 `olive-apricot`（默认，兼容别名「橄榄行踪」）**、珊瑚青绿 `coral-teal`、蓝粉浅彩 `blue-pink`、蓝天绿地 `blue-sky`、柔绿森林 `soft-forest`、粉彩少女 `pastel-girl`、海洋清风 `ocean-breeze`，以及自定义色板 `custom`。用户未指定时使用默认色板；补图或修图沿用工作区已有设置，用户自定义颜色优先，不增加配色询问步骤。换色仅切换色彩映射，不改变已选模板的版式、字号、渐变或透明层次。

## 配置读写

工作区初始化后，配置保存在 `.vivid/config.json`（支持在工作区或其子目录运行）：

```bash
python _utils/vivid_config.py palettes
python _utils/vivid_config.py set palette olive-apricot
```

自定义色板设置 `palette="custom"` 与至少两个 `#RRGGBB` 十六进制色值组成的 `colors` 列表，严格保留用户给定顺序：

```python
from _utils.vivid_config import write_config
write_config(workspace, palette="custom", colors=["#264653", "#2A9D8F", "#E76F51"])
```

## 数据图角色取色与色阶规则

- **分类序列与浅填深边**：`setup_style()` 后从 `pu.PALETTE`、`pu.COLORS`（或 `gallery_theme` 的 `P`、`C`）读取当前色板。预设色板的分类序列由 `vivid_config.categorical_colors()` 按固定 `category_order` 优先取差异明显的颜色；主次、升降、文字、网格与参考线使用对应 `COLORS` 角色。适用柱形、箱线/小提琴或区间带时，沿用配方以 `_lighten(PALETTE[i], 0.4)` 浅色填充搭配 `PALETTE[i]` 原色描边建立层次，不强套于不适用的图型。
- **连续与发散热图色阶**：热图与连续场通过 `_utils.palette_maps` 读取 `palette_colors()` 原序生成连续映射——单向计数/强度使用 `palette_cmap("sequential")`（浅底至主题首色），正负偏差/相关性使用 `palette_cmap("diverging")`（主题首色—中性中心—差异最大主题色，保持中性中心）；多节点插值使用 `palette_stops`，单元格文字可用 `contrast_text` 自动选择黑白对比色。仅在用户明确指定固定科学色图时覆盖默认。
- **硬编码限制与特殊高亮**：常规数据系列禁用 Matplotlib 默认蓝 `#1f77b4`、刺眼基础色名或随意硬编码 HEX；每张图最多允许 2 个与当前主题协调的特殊高亮或参考线 HEX 色值（更多分图型示例可按需参阅 [配色参考](original/resources/assets/shared-scripts/figure_color_reference.md)）。

## 跨通道边界

SVG 架构资产共用项目色板时按 [架构图语义配色](architecture/PALETTE.md) 映射对象身份、浅底深边与状态色；简单流程/方框结构图统一单主色及浅底、批注框白底，物理工程图保留原配色。
