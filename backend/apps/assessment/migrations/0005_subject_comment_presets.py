"""Give every existing school the standard subject-teacher comment presets."""

from django.db import migrations

PRESETS = [
    (80, 100, "Excellent. Keep it up."),
    (70, 79.99, "Very good work."),
    (60, 69.99, "Good. Can do better."),
    (50, 59.99, "Fair. More practice needed."),
    (40, 49.99, "Weak. Needs more effort."),
    (0, 39.99, "Poor. Needs extra help and practice."),
]


def add_presets(apps, schema_editor):
    School = apps.get_model("core", "School")
    CommentBank = apps.get_model("assessment", "CommentBank")
    for school in School.objects.all():
        if CommentBank.objects.filter(school=school, role="subject").exists():
            continue
        for low, high, text in PRESETS:
            CommentBank.objects.create(school=school, role="subject", min_average=low, max_average=high, text=text)


class Migration(migrations.Migration):
    dependencies = [("assessment", "0004_subject_comments")]

    operations = [migrations.RunPython(add_presets, migrations.RunPython.noop)]
