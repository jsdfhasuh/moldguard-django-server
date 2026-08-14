# MoldGuard 知识库与 Django 测试服务器对齐说明

- **版本**：V3.0
- **日期**：2026-08-13
- **知识库基线**：MOLDGUARD-KB-1.2
- **实施计划**：V4.2

## 1. 权威规则

知识库 V1.2 是当前作业、点检、安全要求和故障工时知识的最终解释。Django中的模次、周期、阈值和状态机是业务事实权威；Django不得生成知识正文或用旧知识覆盖平台检索结果。

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

## 4. 检索与回写边界

1. Django通过 `GET /api/v1/work-orders/{work_order_id}/knowledge-context` 返回模具类型、知识画像、关键词和所需知识类型。
2. 平台使用“我的知识库”检索并组装 `catalog_version + items[]`。
3. 平台调用 `POST /api/v1/work-orders/{work_order_id}/knowledge` 提交实际检索结果。
4. Django只校验、规范化、保存和计算知识包哈希；Django不访问平台知识库。
5. Django根据已保存知识包渲染派工邮件和报工页面，并生成 `report_url`。

## 5. 报工链接

Django 生成 `report_url`，并将该链接和已保存的同一知识快照放入 SMTP 邮件；报工页面展示同一快照。员工在该页面上传文字和现场图片，Django 保存后 Webhook 唤醒平台。平台审核必须使用这份锁定快照和全部图片，只回写建议；Django 最终决定正常完成并按矩阵复位、进入异常闭环或要求补充材料。

## 6. 不重复建设

- 知识正文在平台；
- 平台负责检索和组装本工单知识包；
- Django只保存平台提交的本工单实际知识包JSON、知识版本和哈希；
- 22条点检和78条故障工时继续由知识库提供；
- Django保存人员选择的点检结果和故障源表ID。
