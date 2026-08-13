# MoldGuard 知识库 MOLDGUARD-KB-1.2

- **状态**：`FINAL_FROZEN`
- **发布日期**：2026-08-13
- **结构化条目**：239
- **报工表单契约**：`REPORT-FORM-1.0`
- **替代版本**：V0.1、V0.2、V0.3、V0.4、V1.0、V1.1

## 目录说明

| 目录 | 内容 | 用途 |
|---|---|---|
| `upload/` | 两个最终 Markdown | 上传比赛智能体平台知识库 |
| `review/` | 完整冻结版 Markdown | 人工审阅与全文留档 |
| `structured/` | 结构化知识数据 | 程序校验和后续处理 |
| `manifests/` | 发布清单、校验报告、SHA256SUMS | 完整性和版本验证 |

## V1.2 关键内容

- 派工邮件携带本次适用点检知识；
- Django 返回 `report_url` 和“提交报工情况”按钮文字；
- 邮件链接打开 Django 报工页面；
- 定义 `REPORT-FORM-1.0` 正常/异常报工字段；
- 正常报工校验通过后自动完成，并按知识库复位矩阵更新周期；
- 异常报工进入 `ABNORMAL_REPORTED`，继续处理或关联修模；
- 邮件和报工页面使用同一知识快照版本。

## 平台上传

平台只上传：

1. [`upload/01_触发保养标准.md`](upload/01_触发保养标准.md)
2. [`upload/02_保养内容_点检_储放_故障工时与邮件链接报工.md`](upload/02_保养内容_点检_储放_故障工时与邮件链接报工.md)

## 完整性

校验结果为 `PASS`，JSONL 解析错误和重复 `knowledge_id` 均为 0。文件哈希见 [`manifests/SHA256SUMS`](manifests/SHA256SUMS)。
