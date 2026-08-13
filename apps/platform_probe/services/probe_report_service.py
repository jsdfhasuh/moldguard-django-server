from django.utils import timezone

from apps.platform_probe.exceptions import ProbeAPIException
from apps.platform_probe.models import ProbeRun, ProbeStep

CAPABILITIES = [
    ("P01_GET", "GET调用", "证明平台可直接调用动态GET接口", "无"),
    ("P01_POST", "POST调用", "证明平台可提交JSON请求", "无"),
    ("P02", "动态变量", "动态路径和变量连续传递", "失败时需要固定路径适配"),
    ("P03", "嵌套JSON", "多层对象读取与回传", "失败时需要扁平字段适配"),
    ("P04", "数组遍历", "候选、知识和点检数组处理", "失败时需要逐条接口适配"),
    ("P05", "状态流转", "预警、工单、派工和报工连续调用", "决定工作流编排方式"),
    ("P06", "知识检索", "按检索条件命中平台知识库", "可能需要明确关键词"),
    ("P07", "知识回写", "知识条目数组回写Django", "可能需要逐条回写适配"),
    ("P08", "动态邮件", "使用动态收件人与模板变量发送", "可能需要外部邮件服务"),
    ("P09", "邮件回写", "发送状态与消息ID回写", "失败时需平台回调适配"),
    ("P10", "主动报工", "被派工人员主动提交正常报工", "决定正式闭环形态"),
    ("P11", "异常分支", "FAIL点检进入异常报工", "决定异常处理适配"),
    ("P12", "定时调用", "平台定时调用heartbeat", "可能需要Linux cron"),
    ("P13", "重复调用", "重试不重复建单或复位", "平台无需自行去重"),
    ("P14", "能力报告", "生成完整能力矩阵", "无"),
]


def get_probe_run(run_id, *, lock=False):
    queryset = ProbeRun.objects.select_for_update() if lock else ProbeRun.objects.all()
    try:
        return queryset.get(run_id=run_id)
    except ProbeRun.DoesNotExist as exc:
        raise ProbeAPIException("PROBE_RUN_NOT_FOUND", "探测运行不存在", status_code=404) from exc


def expected_context(run):
    return {
        "dynamic_variables": {
            "run_id": run.run_id,
            "mode": run.mode,
            "context_path": f"/api/v1/probe/runs/{run.run_id}/context",
        },
        "nested_json": {
            "mold": {
                "mold_id": "MOLD-TEST-001",
                "maintenance": {
                    "rule_id": "MAINT_TRIGGER_TONNAGE_V1",
                    "threshold": 50000,
                    "required_types": [
                        "MAINTENANCE_STANDARD",
                        "INSPECTION_STANDARD",
                        "SAFETY",
                    ],
                },
            }
        },
        "array_items": [
            {"sequence": 1, "value": "dynamic-path"},
            {"sequence": 2, "value": "nested-json"},
            {"sequence": 3, "value": "array-roundtrip"},
        ],
    }


def record_step(
    run,
    capability_code,
    status,
    *,
    request_snapshot=None,
    response_snapshot=None,
    evidence="",
):
    step, _ = ProbeStep.objects.update_or_create(
        run=run,
        capability_code=capability_code,
        defaults={
            "status": status,
            "request_snapshot_json": request_snapshot or {},
            "response_snapshot_json": response_snapshot or {},
            "evidence": evidence,
        },
    )
    return step


def build_probe_report(run):
    step_map = {step.capability_code: step for step in run.steps.all()}
    matrix = []
    for code, name, default_evidence, default_impact in CAPABILITIES:
        if code == "P14":
            status = ProbeStep.Status.PASS_NATIVE
            evidence = f"GET /api/v1/probe/runs/{run.run_id}/report returned this matrix"
            impact = default_impact
        elif code in step_map:
            step = step_map[code]
            status = step.status
            evidence = step.evidence or default_evidence
            impact = step.response_snapshot_json.get("impact", default_impact)
        else:
            status = ProbeStep.Status.NOT_TESTED
            evidence = "尚未收到平台测试证据"
            impact = default_impact
        matrix.append(
            {
                "capability_code": code,
                "capability": name,
                "status": status,
                "evidence": evidence,
                "impact": impact,
            }
        )

    counts = {status: 0 for status, _ in ProbeStep.Status.choices}
    for item in matrix:
        counts[item["status"]] += 1
    if counts[ProbeStep.Status.NOT_TESTED] == 0:
        if run.status != ProbeRun.Status.COMPLETED:
            run.status = ProbeRun.Status.COMPLETED
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at"])

    return {
        "run": {
            "run_id": run.run_id,
            "platform_name": run.platform_name,
            "tester": run.tester,
            "mode": run.mode,
            "status": run.status,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        },
        "summary": {
            "total": len(matrix),
            "tested": len(matrix) - counts[ProbeStep.Status.NOT_TESTED],
            "counts": counts,
        },
        "capabilities": matrix,
    }
