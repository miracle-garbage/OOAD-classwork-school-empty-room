# 校园空教室预约管理系统 · 系统分析（包图、接口与顺序图）

本目录承接 `../user-case-analysis/` 与 `../class-analysis/`，是系统分析的后续模型部分。内容包括系统逻辑包图、分层依赖规则、接口契约和 4 张核心顺序图，对应报告第 2.3～2.5 节。系统设计部分暂留空，待后续补充。

## 交付内容

| 内容 | 交付物 |
| --- | --- |
| 包图模型 | `系统设计与包图.md` 第 2 节：逻辑包图、包职责、依赖约束与用况追溯；源文件为 `diagrams/package-diagram.puml` |
| 接口设计 | `接口与顺序图设计.md` 第 1 节：REST 接口、请求 / 响应、错误码、幂等、并发与内部端口 |
| 顺序图 | `接口与顺序图设计.md` 第 2 节；`diagrams/sequence-*.puml` 与已导出的 PNG / SVG |

## 文档与图号

| 编号 | 用况 | 源文件 |
| --- | --- | --- |
| 图 2-7 | 系统逻辑包图 | `diagrams/package-diagram.puml` |
| 图 2-8 | UC-03 提交预约申请 | `diagrams/sequence-uc03-submit-reservation.puml` |
| 图 2-9 | UC-06 审批预约申请 | `diagrams/sequence-uc06-approve-request.puml` |
| 图 2-10 | UC-10 签到核验 | `diagrams/sequence-uc10-check-in.puml` |
| 图 2-11 | UC-11 超时未签到自动释放 | `diagrams/sequence-uc11-auto-release.puml` |

建议阅读顺序：先看 `系统设计与包图.md` 的包边界与依赖规则，再看 `接口与顺序图设计.md` 的接口契约和核心交互。

## 重新渲染

在项目根目录执行：

```bash
java -jar class-analysis/tools/plantuml.jar -charset UTF-8 -tpng -o png system-design/diagrams/package-diagram.puml
java -jar class-analysis/tools/plantuml.jar -charset UTF-8 -tsvg -o svg system-design/diagrams/package-diagram.puml
java -jar class-analysis/tools/plantuml.jar -charset UTF-8 -tpng -o png system-design/diagrams/sequence-*.puml
java -jar class-analysis/tools/plantuml.jar -charset UTF-8 -tsvg -o svg system-design/diagrams/sequence-*.puml
```

包图依赖 Graphviz 的 `dot`；没有 Graphviz 时可对包图追加 `-Playout=smetana` 使用 PlantUML 内置布局。顺序图与包图的字体使用 `Noto Sans CJK SC`，避免中文在 PNG / SVG 中显示为方块。

## 文件清单

| 文件 | 说明 |
| --- | --- |
| `系统设计与包图.md` | 系统分析模型主文档：包图、分层规则、端口、用况追溯与建模取舍 |
| `接口与顺序图设计.md` | 接口契约、错误码、内部端口和 4 张核心顺序图 |
| `diagrams/package-diagram.puml` | 图 2-7 包图源文件 |
| `diagrams/sequence-*.puml` | 图 2-8～2-11 顺序图源文件 |
| `diagrams/png/*.png` | 已导出的位图，可直接插入 Word / PPT |
| `diagrams/svg/*.svg` | 已导出的矢量图，排版放大不失真 |

## 模型边界

- 图中的包是逻辑模块，不对应仓库目录，也不强制微服务化；当前可采用模块化单体加独立定时任务。
- 表现层只依赖应用层，应用层只依赖领域层与应用端口；领域层不依赖界面、数据库或第三方 SDK。
- 基础设施层实现应用端口并适配外部系统，启动与配置只在运行时完成装配。
- 对外接口采用 `/api/v1` REST/JSON，命令使用幂等键，可变更资源使用版本号与 `If-Match`。
- 同一教室同时段的最终互斥由数据库区间排除约束保证，不依赖前端或“先查后写”。
- 通知通过 Outbox 异步投递；外部消息失败不回滚预约、审批或自动释放结果。
- 本目录不包含小组成员姓名、学号等个人信息；正式报告及成员分工位于被 `.gitignore` 排除的 `class-private/`。
