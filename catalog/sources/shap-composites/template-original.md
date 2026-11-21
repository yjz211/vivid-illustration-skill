# SHAP完整组合模板

两套由用户效果图重建的完整组合，共用同一个渲染脚本和数据处理函数。原始代码、模型和数据均未提供；这里是可复用重建，不声称获得作者源码。参考图与来源说明见两张卡片。

| ID | 模式 | 适用目的 |
|---|---|---|
| `template.shap_dependence` | `dependence` | 哪些因素重要，特征值与模型归因如何变化？ |
| `template.shap_contribution` | `contribution` | 哪些变量及变量类别贡献较大，归因方向如何分布？ |

选定后直接使用 [完整脚本](../../../templates/shap-composites/plot_shap_composites.py) 的对应模式，保留其专用布局。默认读取当前Vivid项目配色；`--reference-colors`明确选用截图近似色，不影响其他模板。连续颜色表示各特征内部的最小值到最大值，不能跨变量比较原始单位；常数列显示中间色。字体、透明散点、方形标记、双层环和双横轴均由模板保留。

## 输入

先在任务目录执行Vivid bootstrap。准备两份CSV：第一列必须是`sample_id`，随后列为数值特征；`features.csv`存特征值，`shap.csv`存同一批样本、同一模型输出的SHAP值。脚本按唯一编号及列名对齐，拒绝遗漏/重复编号、列名不一致和非有限值。至少3个样本、2个变量。先明确所解释的数据集、模型类别/输出和SHAP单位；多分类模型一次选择一个类别，不能把不同类别的归因混入同一矩阵。

```csv
sample_id,PRE,TEM,EVI
S001,12.3,25.1,0.6
S002,18.2,22.8,0.7
S003,10.9,28.3,0.5
```

以上仅说明特征CSV格式；SHAP值应从实际模型解释器导出，不能用特征值或相关系数替代。模板不负责训练模型或猜测SHAP值。分类编码可绘制，但少于5个不同取值时不画连续趋势；需要可读类别标签时在完整源码中适配。

### 重要性＋蜂群＋依赖图（145）

```text
python "<SKILL>/templates/shap-composites/plot_shap_composites.py" --mode dependence --features features.csv --shap shap.csv --top 15 --panels 8 --output figures/fig_shap_dependence
```

左侧柱形和散点分别使用顶部“mean |SHAP|”和底部“SHAP value”横轴，同一变量行叠加；右侧默认按重要性取前8项、两列排列。`--panels`支持1–12，`--top`支持1–25，按真实变量数截取。右侧横轴为该特征原始输入值，纵轴为SHAP值；灰线为局部线性平滑，仅描述关系，不是因果曲线或阈值检验。M为样本中位数。

默认不推断转折点。确有结果时传`--thresholds-json thresholds.json`：

```json
{"PRE":{"value":18.5,"method":"分段回归得到的断点，方法及数据见分析结果"}}
```

T只表示用户提供的阈值，不代表自动发现的显著转折点。数值须在观测范围内。不要照抄截图中的性能指标；本模板不生成未经提供的R²、MAE、RMSE。

### 重要性＋双层贡献环＋蜂群（146）

```text
python "<SKILL>/templates/shap-composites/plot_shap_composites.py" --mode contribution --features features.csv --shap shap.csv --groups-json groups.json --top 12 --output figures/fig_shap_contribution
```

`groups.json`为每个特征指定一个类别，例如`{"PRE":"Climate","TEM":"Climate","EVI":"Vegetation"}`。须完整覆盖输入列，支持2–6组，建议2–4个有明确含义的组。左侧条形与右侧方形蜂群保持同一排序和行位置；双层环嵌在左侧空白区。内环按组排列单个变量，外环汇总组别，组内变量与柱形同色。若重要性接近，自动扩大横轴显示范围给环图留空，不改变柱值。

重要性为`mean(abs(SHAP), axis=0)`，占比为该值除以**全部输入变量**的重要性总和。只显示top项也不重新归一化；环图仍包含全部变量。组别贡献为所属变量重要性之和，**不同于先合并有符号SHAP再取绝对值**，并非正式的group SHAP。全零SHAP拒绝计算占比。截图中变量名旁括号数值的定义未知，因此不凭空生成这类标注。

## 演示与输出

```text
python "<SKILL>/templates/shap-composites/plot_shap_composites.py" --mode dependence --demo --reference-colors --output figures/fig_shap_dependence_demo
python "<SKILL>/templates/shap-composites/plot_shap_composites.py" --mode contribution --demo --reference-colors --output figures/fig_shap_contribution_demo
```

演示为固定种子320行、12个特征的合成模型，包含非线性主效应和两两交互。按经验边缘分布的乘积背景解析计算interventional SHAP，满足`base_value + sum(SHAP) = prediction`。阈值是模拟模型已知的铰点；领域变量名仅示意，不是原图研究数据。具体模型及计算方法在脚本`demo_data`和输出的`demo-data/PROVENANCE.md`中。真实数据模式绝不补造数值。

每次输出PNG、矢量PDF及数值JSON（排序、重要性、占比、分组/阈值、趋势与归一化说明）；演示另输出可复用CSV与JSON输入。依赖NumPy、Matplotlib及包内Vivid工具，无需安装SHAP即可渲染已计算的SHAP值。

原生宽7.1英寸，建议180毫米通栏使用，此时8pt字体上页约7.99pt；缩成单栏时应减少变量/右侧面板并适配完整源码。长变量名、很多变量或不均衡的分组需检查标签空间。SHAP说明模型归因，不直接证明因果关系。
