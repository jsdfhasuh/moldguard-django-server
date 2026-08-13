from apps.workorders.services.knowledge_service import knowledge_hash


def test_knowledge_hash_is_canonical_for_object_key_order():
    first = {
        "title": "点检包",
        "items": [{"knowledge_id": "CHK-INJ-001", "required": True}],
        "knowledge_snapshot_version": "MOLDGUARD-KB-1.2",
    }
    second = {
        "knowledge_snapshot_version": "MOLDGUARD-KB-1.2",
        "items": [{"required": True, "knowledge_id": "CHK-INJ-001"}],
        "title": "点检包",
    }
    assert knowledge_hash(first) == knowledge_hash(second)
    assert len(knowledge_hash(first)) == 64


def test_knowledge_hash_changes_when_content_changes():
    first = {"items": [{"knowledge_id": "CHK-INJ-001", "required": True}]}
    second = {"items": [{"knowledge_id": "CHK-INJ-001", "required": False}]}
    assert knowledge_hash(first) != knowledge_hash(second)
