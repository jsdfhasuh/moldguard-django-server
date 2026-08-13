# MoldGuard 知识库与 Django 最小测试服务器对齐说明

- **版本**：V2.1
- **日期**：2026-08-13
- **知识库基线**：`MoldGuard_模具保养知识库_上传包V0.1.zip`
- **适用计划**：`docs/plans/2026-08-12-moldguard-django-implementation-plan.md` V4.1
- **服务器定位**：无角色、无鉴权、无历史导入的比赛测试服务器

---

## 1. 最终边界

```text
知识库负责：
保养做什么
点检什么
如何判定
安全要求
验收要求
异常处理参考

Django负责：
什么时候提醒
当前模次和周期基线
工单派给谁
工单当前状态
点检结果
是否验收
周期是否复位
工时和完成率
```

Django不导入完整知识库正文，也不导入历史业务记录。

---

## 2. 当前自动触发规则

Django只使用代码中的两条当前规则：

```text
开发吨位 <1000T  → 50,000模次
开发吨位 >=1000T → 30,000模次
```

知识库中的以下内容只作为说明：

```text
精密/普通/小型模具3万、5万、10万
一保、二保、三保周期
零件级历史周期
外部A/B/C体系
```

平台提示词必须明确：

> 自动保养触发依据只能使用 Django 返回的开发吨位、规则ID和阈值。知识库历史周期不得覆盖 Django 当前规则。

---

## 3. Django向平台返回的知识上下文

```json
{
  "mold_id": "MOLD-001",
  "mold_type": "INJECTION",
  "knowledge_profile_code": "KB-INJECTION-PERIODIC-V1",
  "trigger_rule_id": "MAINT-TONNAGE-LT1000-V1",
  "count_threshold": 50000
}
```

不再返回复杂标签、审批状态、规则冲突或保养等级。

---

## 4. 平台检索内容

平台根据 `knowledge_profile_code` 和 `mold_type` 检索：

- 保养项目；
- 点检清单；
- 安全注意事项；
- 验收标准；
- 异常处理参考。

平台只需生成一份本次工单知识包。

---

## 5. 知识快照最小结构

平台回写：

```json
{
  "catalog_version": "kb-v0.1",
  "items": [
    {
      "knowledge_id": "KB-INS-001",
      "title": "模腔清洁",
      "source_file": "05_模具保养点检标准.md"
    }
  ]
}
```

Django直接保存到：

```text
WorkOrder.knowledge_snapshot_json
```

一个工单只保存最后一份快照，不做多版本、不保存内容哈希、不建立独立知识表。

---

## 6. 点检最小结构

平台从知识库选择适用点检项，回写：

```json
[
  {
    "knowledge_id": "KB-INS-001",
    "item": "模腔清洁",
    "criteria": "无残料、无油污",
    "result": "PASS",
    "note": ""
  }
]
```

Django保存到：

```text
WorkOrder.inspection_items_json
```

不建立点检模板表、点检结果表或图片附件表。

---

## 7. 邮件关系

平台发送邮件。Django只保存最后一次结果：

```text
email_recipient
email_status
email_message_id
email_sent_at
email_error
```

不保存：

```text
邮件主题
抄送
附件
多次发送记录
重试历史
```

---

## 8. 明确删除

```text
知识目录发布模型
规则审批模型
知识条目导入模型
历史记录导入
历史导入复位
故障标准数据库
多版本知识快照
点检照片
知识内容哈希
```

知识包V0.1继续上传到比赛平台，但Django只需要两个知识画像编码：

```text
KB-INJECTION-PERIODIC-V1
KB-SHEET-METAL-PERIODIC-V1
```

---

## 9. 最终结论

知识库和Django的对接只保留三步：

```text
Django返回知识画像
→ 平台检索并发送邮件
→ 平台回写单份知识JSON和邮件结果
```

不建设知识治理系统，不导入历史资料到Django。