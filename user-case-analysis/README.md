# 校园空教室预约管理系统 · 用况分析（作业交付）

本目录是《面向对象设计与分析》课堂作业（学期课设选题）的交付物，可整体拷贝、打包或提交：文档、图表源文件与已渲染图片都在本目录内，不依赖其他文件夹。作业要求来自课堂图片「作业要求1」「作业要求2」，其内容已转录在报告第 0 节。

## 作业要求的判断

- 图片一（PPT）说明"需求分析 → 需求模型 → 健壮分析 → 分析模型"的 OOSE 过程，用况（use case）用于描述需求；
- 图片二（黑板）列出三项交付物：**用况图、用况文档（核心用况）、活动图**；
- 两张图片未指定题目 → 属于学期课设题型，需**自行选题**。

据此选题 **校园空教室预约管理系统**，完成用况分析。

## 交付内容

| 黑板要求 | 交付物 |
| --- | --- |
| ① 用况图 | `用况分析.md` 第 3.3 节 / `diagrams/use-case-diagram.puml`（10 个参与者、17 个用况） |
| ② 用况文档（核心用况） | `用况分析.md` 第 4 节（8 份核心用况规约：UC-01、UC-02、UC-03、UC-06、UC-07、UC-10、UC-11、UC-13），第 3.2 节为 17 个用况清单 |
| ③ 活动图 | `用况分析.md` 第 5 节 / `diagrams/activity-*.puml`（UC-03 提交预约、UC-06 审批、UC-10/UC-11 签到与超时释放） |

## 文件清单

| 文件 | 说明 |
| --- | --- |
| `校园空教室预约管理系统.docx` | **Word 交付物（正式提交版）**：含总体用况图、三人分工表、9 份用况文档、3 张核心活动图 |
| `用况分析.md` | 主报告：作业要求识别 → 需求说明 → 用况模型 → 核心用况文档 → 活动图 → 后续衔接 |
| `diagrams/use-case-diagram.puml` | 用况图源文件（PlantUML） |
| `diagrams/activity-uc03-submit-reservation.puml` | 活动图：UC-03 提交预约申请 |
| `diagrams/activity-uc06-approve-request.puml` | 活动图：UC-06 审批预约申请 |
| `diagrams/activity-uc10-uc11-checkin-release.puml` | 活动图：UC-10 签到核验 / UC-11 超时未签到自动释放 |
| `diagrams/png/*.png` | 已渲染的图片（4 张），可直接插入课程报告 |
| `diagrams/svg/*.svg` | 已渲染的矢量图（4 张），排版时放大不失真 |

## 如何渲染并导出图片（用于插入 Word 报告）

图片已经渲染完成，可直接使用 `diagrams/png`（位图）或 `diagrams/svg`（矢量图）。如需重新渲染：

1. **命令行（已在本机验证）**：先从 https://plantuml.com/download 下载 `plantuml.jar`，再执行 `java -jar plantuml.jar -charset UTF-8 -tpng -o diagrams/png diagrams/*.puml`；SVG 同理，把 `-tpng` 换成 `-tsvg`。（渲染用的 jar 已在使用后删除，未保留在工程中。）
2. **VS Code 扩展**：安装 `jebbs.plantuml` 扩展，打开任一 `.puml` 文件，按 `Alt+D` 预览，右键选择 `Export Current Diagram` 导出 PNG/SVG。
3. **在线渲染**：把 `.puml` 内容粘贴到 https://www.plantuml.com/plantuml ，选择 PNG/SVG 下载。

> 提示：图中有中文，4 个 `.puml` 文件均已设置 `skinparam defaultFontName "Microsoft YaHei"`，并以 `-charset UTF-8` 渲染，避免中文显示为方块。

## 一致性自检要点

- 用况图中每个 `«include»` / `«extend»` 都在第 3.4 节有理由说明；
- 第 4 节每个核心用况的"业务规则"编号均可在第 2.3 节 BR 表中查到；
- 第 5 节活动图与对应核心用况的主事件流、备选流一一对应；
- 附录 A 给出"需求 → 用况 → 交付物"的追溯关系。

## 个人信息说明

`校园空教室预约管理系统.docx` 为正式提交版，按课程要求保留小组成员姓名与学号；本目录其余文件（本 README、`用况分析.md`、`.puml` 源文件及导出的 PNG / SVG 图片）均不包含个人敏感信息。需要修改 Word 交付物内容时，直接编辑该 `.docx` 即可。
