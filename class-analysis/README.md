# 校园空教室预约管理系统 · 类图分析（分析模型交付）

本目录是《面向对象设计与分析》课堂作业（学期课设选题）在**系统分析阶段**的交付物：
把 `../user-case-analysis/` 的**需求模型（用况模型）** 继续推进为**分析模型（类图）**。
文档、图表源文件与已渲染图片都在本目录内，可整体拷贝、打包或提交，不依赖其他文件夹（上游用况分析见 `../user-case-analysis/`）。

## 交付内容

| 内容 | 交付物 |
| --- | --- |
| ① 领域实体类图 | `类图分析.md` 第 3.1 节 / `diagrams/class-diagram-domain.puml`（23 个实体类，含泛化 / 聚合 / 组合 / 关联与多重度） |
| ② 分析类图 | `类图分析.md` 第 3.2 节 / `diagrams/class-diagram-analysis.puml`（8 个边界类、13 个控制类、15 类实体，表达「用况 → 类」映射） |
| ③ 类清单与关系说明 | `类图分析.md` 第 1、2 节（类的识别、类间关系与理由、用况 → 类追溯矩阵） |

## 文件清单

| 文件 | 说明 |
| --- | --- |
| `类图分析.md` | 主报告：阶段衔接 → 类识别 → 类关系 → 类图 → 关键设计 → 追溯矩阵 |
| `diagrams/class-diagram-domain.puml` | 图 1 领域实体类图源文件（PlantUML） |
| `diagrams/class-diagram-analysis.puml` | 图 2 分析类图源文件（PlantUML） |
| `diagrams/png/*.png` | 已渲染的位图（2 张），可直接插入 Word / PPT |
| `diagrams/svg/*.svg` | 已渲染的矢量图（2 张），排版放大不失真 |
| `tools/plantuml.jar` | PlantUML 1.2026.8 渲染器（本地工具，已被 `.gitignore` 的 `*.jar` 规则忽略，不入库） |
| `tools/render_offline.py` | 离线渲染脚本（无 `plantuml.jar` 且不能联网时的后备方案） |

## 如何渲染并导出图片

两张图均由 **PlantUML 1.2026.8 + Graphviz** 渲染完成，可直接使用 `diagrams/png`（位图）或 `diagrams/svg`（矢量图）。如需重新渲染：

1. **命令行（本目录已附 `tools/plantuml.jar`）**：

   ```bash
   # 在 class-analysis/ 目录下执行；-o 相对于源文件所在目录（即 diagrams/）
   java -jar tools/plantuml.jar -charset UTF-8 -tpng -o png diagrams/*.puml
   java -jar tools/plantuml.jar -charset UTF-8 -tsvg -o svg diagrams/*.puml
   ```

   类图依赖 Graphviz 的 `dot`；`dot` 不在 PATH 时可用 `GRAPHVIZ_DOT=/path/to/dot java -jar ...` 指定。
2. **VS Code 扩展**：安装 `jebbs.plantuml`，打开任一 `.puml` 文件，按 `Alt+D` 预览，右键 `Export Current Diagram` 导出 PNG / SVG。
3. **离线后备（可选）**：`tools/render_offline.py` 可在没有 Java / `plantuml.jar` 且不能联网时生成同模型图片：
   `python3 tools/render_offline.py`（依赖本机 LibreOffice 把 SVG 转 PNG）。

> 提示：两个 `.puml` 文件均已设置 `skinparam defaultFontName "Microsoft YaHei"`，并以 `-charset UTF-8` 渲染，避免中文显示为方块。

## 一致性自检要点

- 图 1 中每个实体类都能追溯到 `../user-case-analysis/用况分析.md` 的“涉及实体”或第 6 节的实体类映射；
- 图 1 的泛化结构与用况图的「学生 / 教师 → 预约用户」参与者泛化一致；
- 图 2 的每个控制类对应 1~2 个用况，`预约规则校验器` 与 UC-04 的 «include» 关系一一对应；
- 第 5 节的「用况 → 类」追溯矩阵覆盖全部 17 个用况；
- 类关系中的业务依据（BR-XX）均可在上游 `用况分析.md` 第 2.3 节查到。

## 个人信息说明

本目录文件（本 README、`类图分析.md`、`.puml` 源文件及导出的 PNG / SVG）均不包含个人敏感信息，可安全提交 / 上传。
