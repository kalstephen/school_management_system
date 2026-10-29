"""Requisitions raised before the approval chain: give open ones a short route."""

from django.db import migrations


def route_open_requisitions(apps, schema_editor):
    Requisition = apps.get_model("finance", "Requisition")
    for requisition in Requisition.objects.filter(route=[], status__in=["pending", "approved"]):
        requisition.route = ["head_teacher", "finance"]
        requisition.step = 0 if requisition.status == "pending" else 1
        requisition.save(update_fields=["route", "step"])


class Migration(migrations.Migration):
    dependencies = [("finance", "0003_requisition_journey")]

    operations = [migrations.RunPython(route_open_requisitions, migrations.RunPython.noop)]
