"""Write the audit trail: every create, edit and delete with before and after values."""

import datetime
import decimal

from django.db.models.fields.files import FieldFile

from .context import get_current_user
from .models import AccessLog, AuditLog

SKIP_FIELDS = {"updated_at", "updated_by_id", "created_at", "created_by_id"}


def _plain(value):
    if isinstance(value, (datetime.date, datetime.datetime, datetime.time, decimal.Decimal)):
        return str(value)
    if isinstance(value, FieldFile):
        return value.name or ""
    return value


def _snapshot(instance):
    data = {}
    for field in instance._meta.concrete_fields:
        if field.attname in SKIP_FIELDS or field.name in instance.audit_exclude:
            continue
        data[field.attname] = _plain(getattr(instance, field.attname))
    return data


def _user():
    user = get_current_user()
    return user if user is not None and user.is_authenticated else None


def _entity(instance):
    return f"{instance._meta.app_label}.{instance._meta.model_name}"


def record_save(instance, old):
    new = _snapshot(instance)
    if old is None:
        action = AuditLog.Action.CREATE
        changes = {k: [None, v] for k, v in new.items() if v not in (None, "")}
    else:
        action = AuditLog.Action.UPDATE
        changes = {}
        for key, value in new.items():
            before = _plain(old.get(key))
            if before != value:
                changes[key] = [before, value]
        if not changes:
            return
    AuditLog.objects.create(
        school_id=instance.school_id,
        user=_user(),
        entity=_entity(instance),
        object_id=str(instance.pk),
        object_repr=str(instance)[:200],
        action=action,
        changes=changes,
    )


def record_delete(instance):
    AuditLog.objects.create(
        school_id=instance.school_id,
        user=_user(),
        entity=_entity(instance),
        object_id=str(instance.pk),
        object_repr=str(instance)[:200],
        action=AuditLog.Action.DELETE,
        changes={k: [v, None] for k, v in _snapshot(instance).items() if v not in (None, "")},
    )


def log_access(school, resource, object_id):
    AccessLog.objects.create(school=school, user=_user(), resource=resource, object_id=str(object_id))
