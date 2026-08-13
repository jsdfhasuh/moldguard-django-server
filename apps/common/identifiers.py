import uuid

from django.utils import timezone


def new_identifier(prefix):
    return f"{prefix}-{timezone.localdate():%Y%m%d}-{uuid.uuid4().hex[:12].upper()}"
