# MoldGuard 知识库

本目录保存 MoldGuard 模具保养智能体的**版本化知识库交付物**。知识库正文与 Django 业务代码分离管理；Django 只实现业务数据、触发计算、工单与报工状态。

## 当前版本

```text
MOLDGUARD-KB-1.2
状态：FINAL_FROZEN
发布日期：2026-08-13
结构化条目：239
```

当前版本入口：

- [发布说明](releases/MOLDGUARD-KB-1.2/README.md)
- [比赛平台上传文件](releases/MOLDGUARD-KB-1.2/upload/)
- [完整人工审阅稿](releases/MOLDGUARD-KB-1.2/review/)
- [结构化数据说明](releases/MOLDGUARD-KB-1.2/structured/)
- [校验与发布清单](releases/MOLDGUARD-KB-1.2/manifests/)

## 使用约定

比赛平台知识库只上传 `upload/` 下的两个 Markdown 文件：

```text
01_触发保养标准.md
02_保养内容_点检_储放_故障工时与邮件链接报工.md
```

不要同时上传完整审阅稿，否则会造成重复召回。结构化 JSONL、校验报告和发布清单用于程序校验与版本追溯，不作为普通 RAG 文档上传。

发生业务规则、字段或流程冲突时，以当前版本的发布清单和知识正文为最终解释。
