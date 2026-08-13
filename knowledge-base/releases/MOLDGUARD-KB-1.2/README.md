# MoldGuard 知识库 MOLDGUARD-KB-1.2

- **状态**：`FINAL_FROZEN`
- **发布日期**：2026-08-13
- **结构化条目**：239
- **报工表单契约**：`REPORT-FORM-1.0`
- **替代版本**：V0.1、V0.2、V0.3、V0.4、V1.0、V1.1

## 仓库保存内容

本仓库不保存 ZIP 交付包，只保存解压后的最终文档和校验资料：

| 目录 | 内容 | 用途 |
|---|---|---|
| `upload/` | 两个最终 Markdown | 权威知识正文；上传比赛智能体平台 |
| `manifests/` | 发布清单与校验报告 | 完整性、条目数量和版本验证 |
| `structured/` | 原结构化 JSONL 的元数据说明 | 记录条目数量、文件名和 SHA-256 |

完整冻结版不再重复存放。它由 `upload/01` 全文与 `upload/02` 的第二部分共同组成，避免仓库中出现重复知识正文。

## V1.2 关键内容

- 派工邮件携带本次适用点检知识；
- Django 返回 `report_url` 和“提交报工情况”按钮文字；
- 邮件链接打开 Django 报工页面；
- 定义 `REPORT-FORM-1.0` 正常/异常报工字段；
- 正常报工校验通过后自动完成，并按知识库复位矩阵更新周期；
- 异常报工进入 `ABNORMAL_REPORTED`，继续处理或关联修模；
- 邮件和报工页面使用同一知识快照版本。

## 比赛平台上传

平台只上传：

1. [`upload/01_触发保养标准.md`](upload/01_触发保养标准.md)
2. [`upload/02_保养内容_点检_储放_故障工时与邮件链接报工.md`](upload/02_保养内容_点检_储放_故障工时与邮件链接报工.md)

不要把校验报告、发布清单或结构化数据说明上传为普通 RAG 文档。

## 完整性

校验结果为 `PASS`，原始 JSONL 共 239 条，解析错误与重复 `knowledge_id` 均为 0。详见：

- [`manifests/MoldGuard_KB_V1.2_校验报告.json`](manifests/MoldGuard_KB_V1.2_校验报告.json)
- [`manifests/MoldGuard_KB_V1.2_发布清单.json`](manifests/MoldGuard_KB_V1.2_发布清单.json)
