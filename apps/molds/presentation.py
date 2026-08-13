def mold_data(mold):
    return {
        "mold_id": mold.mold_id,
        "mold_name": mold.mold_name,
        "mold_type": mold.mold_type,
        "effective_mold_cycles": mold.effective_mold_cycles,
        "baseline_effective_mold_cycles": mold.baseline_effective_mold_cycles,
        "cycle_mold_cycles": mold.cycle_mold_cycles,
        "baseline_maintenance_at": mold.baseline_maintenance_at.isoformat(),
        "cycle_version": mold.cycle_version,
        "first_production_at": mold.first_production_at.isoformat()
        if mold.first_production_at
        else None,
        "development_tonnage": str(mold.development_tonnage)
        if mold.development_tonnage is not None
        else None,
        "mold_category": mold.mold_category,
        "mold_type_code": mold.mold_type_code,
        "level_1_location": mold.level_1_location,
        "level_2_location": mold.level_2_location,
        "production_line": mold.production_line,
        "output_updated_at": mold.output_updated_at.isoformat() if mold.output_updated_at else None,
        "status": mold.status,
        "knowledge_profile_code": mold.knowledge_profile_code,
        "created_at": mold.created_at.isoformat(),
        "updated_at": mold.updated_at.isoformat(),
    }


def alert_data(alert):
    return {
        "alert_id": alert.alert_id,
        "mold_id": alert.mold_id,
        "primary_rule_id": alert.primary_rule_id,
        "matched_rule_ids": alert.matched_rule_ids_json,
        "alert_type": alert.alert_type,
        "cycle_version": alert.cycle_version,
        "cycle_mold_cycles_snapshot": alert.cycle_mold_cycles_snapshot,
        "threshold_count": alert.threshold_count,
        "trigger_reason": alert.trigger_reason,
        "status": alert.status,
        "dedupe_key": alert.dedupe_key,
        "triggered_at": alert.triggered_at.isoformat(),
        "closed_at": alert.closed_at.isoformat() if alert.closed_at else None,
        "work_order_ids": [item.work_order_id for item in alert.work_orders.all()],
    }
