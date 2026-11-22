#!/usr/bin/env python3
"""Lightweight bilingual search CLI for the 148 Vivid data figure recipes & templates.

Usage:
    python scripts/search_figure.py "SHAP 特征归因" --limit 8
    python scripts/search_figure.py "raincloud distribution" --category distribution
    python scripts/search_figure.py "3d surface" --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "catalog" / "selection-index.jsonl"

# Exact / tight bilingual concept synonyms
EXACT_SYNONYMS: list[list[str]] = [
    ["弦图", "和弦", "和弦图", "chord"],
    ["桑基", "桑基图", "流向图", "sankey"],
    ["雨云", "雨云图", "半小提琴", "raincloud"],
    ["小提琴", "小提琴图", "violin"],
    ["山脊", "山脊图", "密度山脊", "ridgeline", "joyplot"],
    ["核密度", "密度轮廓", "kde", "density"],
    ["分布", "数据分布", "distribution"],
    ["直方", "直方图", "histogram", "hist"],
    ["箱线", "箱线图", "箱型图", "boxplot"],
    ["相关", "相关性", "相关矩阵", "correlation", "pearson", "corr"],
    ["热图", "热力", "热力图", "矩阵热图", "heatmap"],
    ["混淆矩阵", "分类矩阵", "confusion", "confusion_matrix"],
    ["三维", "立体", "三维图", "3d"],
    ["曲面", "响应面", "损失地形", "surface"],
    ["体绘制", "体渲染", "标量体", "volume"],
    ["等值面", "isosurface"],
    ["等高线", "等值线", "contour"],
    ["涡旋", "向量场", "锥体", "cone", "vortex"],
    ["时间", "时序", "时间序列", "timeseries", "time_series"],
    ["趋势", "走势", "演化", "trend"],
    ["预测", "预报", "拟合预测", "forecast", "forecasting", "prediction"],
    ["空间", "地理", "地图", "省级", "分级地图", "spatial", "map", "choropleth", "geojson"],
    ["空间自相关", "局部聚类", "moran", "lisa"],
    ["轨迹", "迁移", "重心迁移", "trajectory", "migration"],
    ["网络", "拓扑", "社区网络", "连线网络", "network", "topology"],
    ["解释", "可解释", "归因", "特征归因", "特征贡献", "shap", "attribution", "explainability"],
    ["特征", "重要性", "特征重要性", "feature", "importance", "beeswarm", "蜂群"],
    ["部分依赖", "个体响应", "pdp", "ice", "dependence"],
    ["环形", "圆环", "环形图", "甜甜圈", "嵌套环", "donut", "nested_donut"],
    ["极坐标", "径向", "同心环", "圆弧", "polar", "radial", "concentric", "arc"],
    ["雷达", "雷达图", "蜘蛛图", "能力轮廓", "radar"],
    ["旭日", "旭日图", "层级环", "sunburst"],
    ["玫瑰", "玫瑰图", "南丁格尔", "rose"],
    ["对比", "比较", "方法对比", "compare", "comparison", "benchmark"],
    ["柱状", "柱状图", "条形", "条形图", "分组柱", "堆叠柱", "bar", "bars", "barh", "grouped_bar", "stacked_bar"],
    ["误差", "误差棒", "置信带", "置信区间", "不确定性", "error", "errorbar", "uncertainty", "ci"],
    ["回归", "线性回归", "分位数回归", "regression", "ols", "quantile"],
    ["因果", "双重差分", "平行趋势", "事件研究", "安慰剂", "causal", "did", "event_study", "parallel_trends", "placebo"],
    ["森林", "森林图", "效应区间", "异质性", "荟萃", "forest", "subgroup_forest", "meta"],
    ["瀑布", "瀑布图", "增减分解", "消融", "waterfall", "ablation"],
    ["棒棒糖", "哑铃", "斜率图", "名次轨迹", "排名", "lollipop", "dumbbell", "slope", "bump", "ranking"],
    ["优化", "收敛", "收敛曲线", "帕累托", "前沿", "龙卷风", "可行域", "optimization", "convergence", "pareto", "tornado", "feasible"],
    ["聚类", "降维", "主成分", "双标图", "嵌入", "cluster", "kmeans", "pca", "biplot", "tsne", "umap"],
    ["散点", "气泡", "六边形", "成对关系", "散点矩阵", "scatter", "bubble", "hexbin", "pair_plot", "pairplot"],
    ["河流", "河流图", "流带", "面积", "堆叠面积", "地平线", "streamgraph", "area", "horizon"],
    ["生存", "风险表", "漏斗", "一致性", "校准", "残差", "甘特", "kaplan", "survival", "funnel", "bland_altman", "calibration", "residual", "gantt", "roc"],
]

# Broader family expansion for related chart discovery
FAMILY_SYNONYMS: list[list[str]] = [
    ["分布", "小提琴", "雨云", "山脊", "violin", "raincloud", "ridgeline", "kde"],
    ["相关", "热图", "热力", "correlation", "heatmap"],
    ["三维", "立体", "曲面", "3d", "surface", "volume", "isosurface"],
    ["时间", "趋势", "预测", "timeseries", "forecast", "trend"],
    ["空间", "地图", "轨迹", "map", "choropleth", "spatial"],
    ["网络", "弦图", "桑基", "network", "chord", "sankey"],
    ["解释", "特征", "归因", "shap", "importance"],
    ["环形", "极坐标", "雷达", "radial", "polar", "radar"],
    ["对比", "柱状", "误差", "bar", "comparison", "error"],
    ["回归", "因果", "森林图", "forest", "regression", "event_study"],
]

CATEGORY_TAGS: dict[str, set[str]] = {
    "compare": {"比较", "排序", "变化", "分组", "柱状"},
    "comparison": {"比较", "排序", "变化", "分组", "柱状"},
    "distribution": {"分布", "密度"},
    "relation": {"关联", "相关", "关系", "散点", "矩阵", "聚类", "降维"},
    "correlation": {"关联", "相关", "矩阵"},
    "timeseries": {"趋势", "时间", "预测", "周期", "调度", "多序列"},
    "time": {"趋势", "时间", "预测", "周期", "调度", "多序列"},
    "trend": {"趋势", "时间", "多序列"},
    "spatial": {"空间"},
    "map": {"空间"},
    "3d": {"三维", "曲面", "标量场", "向量场", "浮雕"},
    "model": {"解释", "诊断", "预测", "机器学习", "训练", "分类", "因果", "误差"},
    "explain": {"解释", "机器学习"},
    "composition": {"组成", "层级", "流向", "流量"},
    "multipanel": {"组合"},
    "composite": {"组合"},
    "polar": {"极坐标"},
    "radial": {"极坐标"},
    "network": {"网络", "流向", "流量", "关系"},
    "optimization": {"优化"},
    "causal": {"因果"},
}

ID_PREFIXES = {"basic", "advanced", "empirical", "academic", "competition", "screenshot", "template"}

_ZH_STOP_BIGRAMS = {"的展", "展示", "用于", "以及", "如何", "怎样", "哪些", "是否", "每个", "多个", "不同"}


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def load_entries(index_path: Path = INDEX_PATH) -> list[dict]:
    entries: list[dict] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def terms(text: str) -> set[str]:
    low = text.lower()
    result: set[str] = set()
    # Joined tokens (e.g. event_study, grouped_bar) + segmented word tokens (e.g. event, study, 3d)
    for tok in re.findall(r"[a-z0-9][a-z0-9_.-]*", low):
        result.add(tok)
    for word in re.findall(r"[a-z0-9]+", low):
        if len(word) >= 2:
            result.add(word)
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        result.add(run)
        for i in range(len(run) - 1):
            bg = run[i : i + 2]
            if bg not in _ZH_STOP_BIGRAMS:
                result.add(bg)
    return result


def _is_ascii_token(tok: str) -> bool:
    return all(ord(ch) < 128 for ch in tok)


def _prepare_field(text: str) -> tuple[str, set[str], set[str]]:
    low = text.lower()
    words = set(re.findall(r"[a-z0-9]+", low))
    joined = set(re.findall(r"[a-z0-9][a-z0-9_.-]*", low))
    return low, words, joined


def _token_in_field(tok: str, field: tuple[str, set[str], set[str]]) -> bool:
    low, words, joined = field
    if not _is_ascii_token(tok):
        return tok in low
    if tok in words or tok in joined:
        return True
    if f"{tok}s" in words or (tok.endswith("s") and len(tok) > 3 and tok[:-1] in words):
        return True
    if len(tok) >= 4 and any(w.startswith(tok) for w in words):
        return True
    return False


def _matches_category(entry: dict, category: str) -> bool:
    cat = category.strip().lower()
    if not cat:
        return True
    prefix = entry["id"].split(".", 1)[0].lower()
    if cat in ID_PREFIXES:
        return prefix == cat
    entry_tags = set(entry.get("tags", []))
    if cat in CATEGORY_TAGS:
        if entry_tags & CATEGORY_TAGS[cat]:
            return True
        if cat == "3d" and "3d" in entry["id"].lower():
            return True
        if cat in ("multipanel", "composite") and prefix == "template":
            return True
        return False
    return any(cat in t.lower() for t in entry_tags) or cat in prefix


def _expand_synonyms(query_low: str, q_terms: set[str]) -> tuple[set[str], set[str]]:
    tight: set[str] = set()
    broad: set[str] = set()
    for group in EXACT_SYNONYMS:
        if any(w.lower() in query_low or w.lower() in q_terms for w in group):
            for w in group:
                tight.add(w.lower())
    for group in FAMILY_SYNONYMS:
        if any(w.lower() in query_low or w.lower() in q_terms for w in group):
            for w in group:
                broad.add(w.lower())
    tight -= q_terms
    broad -= q_terms | tight
    return tight, broad


def rank(
    query: str = "",
    entries: list[dict] | None = None,
    limit: int = 8,
    category: str | None = None,
) -> list[dict]:
    items = entries if entries is not None else load_entries()
    q_raw = query.strip()
    q_low = q_raw.lower()
    q_terms = terms(q_raw) if q_raw else set()
    tight_syn, broad_syn = _expand_synonyms(q_low, q_terms) if q_raw else (set(), set())

    ranked: list[tuple[int, dict]] = []
    for entry in items:
        if category and not _matches_category(entry, category):
            continue

        identity_text = " ".join(
            [entry["id"], entry.get("display_name", ""), " ".join(entry.get("aliases", []))]
        )
        tags_text = " ".join(entry.get("tags", []))
        med_text = f"{entry.get('purpose', '')} {entry.get('composition', '')}"
        low_text = " ".join(
            [
                " ".join(entry.get("visual_features", [])),
                " ".join(entry.get("data_requirements", [])),
            ]
        )

        f_id = _prepare_field(identity_text)
        f_tags = _prepare_field(tags_text)
        f_med = _prepare_field(med_text)
        f_low = _prepare_field(low_text)

        score = 0
        if q_raw:
            if q_low in f_id[0]:
                score += 12
            for t in q_terms:
                if _token_in_field(t, f_id):
                    score += 8
                elif _token_in_field(t, f_tags):
                    score += 5
                elif _token_in_field(t, f_med):
                    score += 3
                elif _token_in_field(t, f_low):
                    score += 1

            for s in tight_syn:
                if _token_in_field(s, f_id):
                    score += 4
                elif _token_in_field(s, f_tags):
                    score += 3
                elif _token_in_field(s, f_med):
                    score += 1

            for b in broad_syn:
                if _token_in_field(b, f_id) or _token_in_field(b, f_tags):
                    score += 1

            if score == 0:
                continue

        ranked.append((score, entry))

    ranked.sort(key=lambda pair: (-pair[0], pair[1].get("number", 9999), pair[1]["id"]))
    out: list[dict] = []
    for score, entry in ranked[: max(limit, 0)]:
        card_rel = f"catalog/{entry['card_path']}"
        preview_rel = f"catalog/{entry['preview']}"
        out.append(
            {
                "score": score,
                **entry,
                "card": card_rel,
                "preview_path": preview_rel,
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query", nargs="?", default="", help="Bilingual intent, chart type, or data shape query")
    ap.add_argument(
        "--category",
        help="Optional category filter (compare|distribution|relation|timeseries|spatial|3d|model|composition|polar|network|optimization|causal or ID prefix)",
    )
    ap.add_argument("--limit", type=int, default=8, help="Max candidates to return (default: 8)")
    ap.add_argument("--json", action="store_true", help="Output JSON list")
    args = ap.parse_args(argv)

    results = rank(args.query, limit=args.limit, category=args.category)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    if not results:
        print(
            "No matching figure recipe. Try broader keywords (e.g. compare / distribution / 3d / heatmap) "
            "or omit --category."
        )
        return 0

    for item in results:
        reqs = "; ".join(item.get("data_requirements", []))
        tags_str = ", ".join(item.get("tags", []))
        print(
            f"#{item['number']} | {item['id']} | {item['display_name']} | score={item['score']} [{tags_str}]\n"
            f"  purpose: {item.get('purpose', '')}\n"
            f"  data: {reqs}\n"
            f"  card: {item['card']}\n"
            f"  preview: {item['preview_path']}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
