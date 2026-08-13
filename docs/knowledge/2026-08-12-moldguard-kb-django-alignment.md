# MoldGuard 知识库与 Django 测试服务器对齐说明

- **版本**：V3.0
- **日期**：2026-08-13
- **知识库基线**：MOLDGUARD-KB-1.2
- **实施计划**：V4.2

## 1. 权威规则

知识库 V1.2 是当前触发、作业、点检、故障工时和直接报工流程的最终解释。Django不得使用旧决策覆盖知识库。

## 2. 平台上传文件

上传：

```text
01_触发保养标准.md
02_保养内容_点检_储放_故障工时与邮件链接报工.md
```

JSONL用于校验和字段契约，不需要作为普通RAG文档重复上传。

## 3. 字段同步

知识库和Django统一使用：

```text
effective_mold_cycles
baseline_effective_mold_cycles
baseline_maintenance_at
cycle_mold_cycles
first_production_at
development_tonnage
mold_category
mold_type_code
level_1_location
level_2_location
knowledge_snapshot_version
report_url
report_type
inspection_results
actual_work_hours
```

## 4. 报工链接

Django返回 `report_url`；平台把本次点检知识和链接放入邮件；报工页面展示同一快照。正常报工完成并按矩阵复位，异常报工进入异常闭环。

## 5. 不重复建设

- 知识正文在平台；
- Django只保存本工单实际知识包JSON和知识版本；
- 22条点检和78条故障工时继续由知识库提供；
- Django保存人员选择的点检结果和故障源表ID。
