# MoldGuard 知识库

本目录保存 MoldGuard 模具保养智能体的**版本化知识库正文和校验资料**。知识库与 Django 业务代码分离管理；Django只实现业务数据、触发计算、工单和报工状态。

## 当前版本

```text
MOLDGUARD-KB-1.2
状态：FINAL_FROZEN
发布日期：2026-08-13
结构化条目：239
```

当前版本入口：

- [发布说明](releases/MOLDGUARD-KB-1.2/README.md)
- [比赛平台上传文档](releases/MOLDGUARD-KB-1.2/upload/)
- [校验与发布清单](releases/MOLDGUARD-KB-1.2/manifests/)
- [结构化数据元信息](releases/MOLDGUARD-KB-1.2/structured/)

## 仓库存储原则

- 不上传 ZIP 交付包；
- 保存解压后的最终 Markdown 文档；
- 保存发布清单和校验报告；
- 不重复保存“完整冻结版”全文，避免同一知识在仓库中出现两份；
- 原始 JSONL 的条目数量和哈希保存在 `structured/` 与校验报告中。

## 比赛平台上传

比赛平台知识库只上传：

```text
01_触发保养标准.md
02_保养内容_点检_储放_故障工时与邮件链接报工.md
```

不要上传发布清单、校验报告或结构化数据说明，避免无关内容进入 RAG 检索。

发生业务规则、字段或流程冲突时，以 `MOLDGUARD-KB-1.2` 的两个权威 Markdown 正文为最终解释。
