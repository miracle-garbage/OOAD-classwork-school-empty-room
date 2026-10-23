# 校园空教室预约管理系统 · 接口设计与顺序图

本目录承接 `../user-case-analysis/` 与 `../class-analysis/`，把分析模型推进到系统设计阶段，集中给出接口契约和 4 张核心顺序图。

## 交付内容

| 内容 | 交付物 |
| --- | --- |
| 接口设计 | `接口与顺序图设计.md` 第 2 节：REST 接口、请求 / 响应、错误码、幂等、并发与内部端口 |
| 顺序图 | `接口与顺序图设计.md` 第 3 节；`diagrams/sequence-*.puml` 与已导出的 PNG / SVG |

## 核心顺序图

| 编号 | 用况 | 源文件 |
| --- | --- | --- |
| 图 3-1 | UC-03 提交预约申请 | `diagrams/sequence-uc03-submit-reservation.puml` |
| 图 3-2 | UC-06 审批预约申请 | `diagrams/sequence-uc06-approve-request.puml` |
| 图 3-3 | UC-10 签到核验 | `diagrams/sequence-uc10-check-in.puml` |
| 图 3-4 | UC-11 超时未签到自动释放 | `diagrams/sequence-uc11-auto-release.puml` |

## 重新渲染

在项目根目录执行：

```bash
java -jar class-analysis/tools/plantuml.jar -charset UTF-8 -tpng -o png system-design/diagrams/*.puml
java -jar class-analysis/tools/plantuml.jar -charset UTF-8 -tsvg -o svg system-design/diagrams/*.puml
```

图的字体使用 `Noto Sans CJK SC`，避免中文在 PNG / SVG 中显示为方块。

## 设计边界

- 对外接口采用 `/api/v1` REST/JSON，命令使用幂等键，可变更资源使用版本号与 `If-Match`。
- 同一教室同时段的最终互斥由数据库区间排除约束保证，不依赖前端或“先查后写”。
- 通知通过 Outbox 异步投递；外部消息失败不回滚预约、审批或自动释放结果。
- 本目录不包含小组成员姓名、学号等个人信息；正式报告及成员分工位于被 `.gitignore` 排除的 `class-private/`。
