from django.utils import timezone


def school_access(school):
    """'full', 'read_only' (expired: view and export only) or 'suspended'.
    A school without a subscription row is treated as full access (self-hosted)."""
    from .models import Subscription

    sub = Subscription.objects.filter(school=school).first()
    if sub is None:
        return "full"
    if sub.status == Subscription.Status.SUSPENDED:
        return "suspended"
    if sub.status == Subscription.Status.EXPIRED or sub.ends_on < timezone.localdate():
        return "read_only"
    return "full"


def set_module(school, module, enabled, user=None, effective_from=None):
    from .models import ModuleChangeLog, SchoolModule

    row, _ = SchoolModule.objects.get_or_create(school=school, module=module)
    row.enabled = enabled
    row.effective_from = effective_from
    row.changed_by = user
    row.save()
    ModuleChangeLog.objects.create(
        school=school, module=module, enabled=enabled, effective_from=effective_from, changed_by=user
    )
    return row


def apply_plan(school, plan, user=None, chosen_addons=()):
    """Switch on the add-ons a plan includes (plus the school's chosen ones)."""
    from apps.core.modules import ADDON_MODULES

    chosen = list(chosen_addons)[: plan.addon_choices]
    wanted = set(plan.included_addons) | set(chosen)
    for module in ADDON_MODULES:
        set_module(school, module, module in wanted, user=user)
