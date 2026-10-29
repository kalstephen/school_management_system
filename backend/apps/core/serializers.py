from rest_framework import serializers

AUDIT_FIELDS = ("school", "created_by", "updated_by", "created_at", "updated_at")


class SchoolOwnedSerializer(serializers.ModelSerializer):
    """Hides audit columns from writes and limits every related-record choice to the
    active school, so a user cannot link to another school's records by id."""

    def get_fields(self):
        fields = super().get_fields()
        for name in AUDIT_FIELDS:
            if name in fields:
                fields[name].read_only = True
        request = self.context.get("request")
        school = getattr(request, "school", None)
        if school is not None:
            for field in fields.values():
                target = getattr(field, "child_relation", field)
                queryset = getattr(target, "queryset", None)
                if queryset is not None and hasattr(queryset.model, "school_id"):
                    target.queryset = queryset.filter(school=school)
        return fields


class LabelField(serializers.CharField):
    """Read-only display string for a related record (e.g. a learner's name in a list)."""

    def __init__(self, source, **kwargs):
        super().__init__(source=source, read_only=True, **kwargs)
