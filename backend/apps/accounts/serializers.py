from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.core.serializers import SchoolOwnedSerializer

from .models import Membership, PermissionGrant, RoleAssignment, User
from .roles import ROLE_LABELS


class LoginSerializer(serializers.Serializer):
    portal = serializers.ChoiceField(choices=["school", "platform"], default="school")
    school_code = serializers.CharField(
        required=False, allow_blank=True, help_text="School ID, e.g. NewHope-003"
    )
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value


class RoleAssignmentSerializer(SchoolOwnedSerializer):
    role_label = serializers.SerializerMethodField()

    class Meta:
        model = RoleAssignment
        fields = ["id", "membership", "role", "role_label", "scope_type", "scope_id"]

    def get_role_label(self, obj):
        return ROLE_LABELS.get(obj.role, obj.role)

    def validate(self, attrs):
        scope_type = attrs.get("scope_type", getattr(self.instance, "scope_type", "school"))
        scope_id = attrs.get("scope_id", getattr(self.instance, "scope_id", None))
        if scope_type != "school" and not scope_id:
            raise serializers.ValidationError(
                {"scope_id": "Choose the class, department or store for this role."}
            )
        return attrs


class MembershipSerializer(SchoolOwnedSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username")
    first_name = serializers.CharField(source="user.first_name", allow_blank=True, required=False)
    last_name = serializers.CharField(source="user.last_name", allow_blank=True, required=False)
    email = serializers.EmailField(source="user.email", allow_blank=True, required=False)
    phone = serializers.CharField(source="user.phone", allow_blank=True, required=False)
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)
    roles = RoleAssignmentSerializer(many=True, read_only=True)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id",
            "user_id",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "password",
            "title",
            "is_active",
            "roles",
            "modules",
            "last_login",
        ]

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_modules(self, value):
        """A person can only inherit modules the school has."""
        from apps.core.modules import ALL_MODULES, enabled_modules

        school = getattr(self.context.get("request"), "school", None)
        unknown = [m for m in value if m not in ALL_MODULES]
        if unknown:
            raise serializers.ValidationError(f"Unknown module(s): {', '.join(unknown)}.")
        if school is not None:
            outside = sorted(set(value) - set(enabled_modules(school)))
            if outside:
                raise serializers.ValidationError(
                    f"The school does not have: {', '.join(ALL_MODULES[m] for m in outside)}."
                )
        return value

    def create(self, validated_data):
        user_data = validated_data.pop("user")
        password = validated_data.pop("password", None)
        user, created = User.objects.get_or_create(username=user_data["username"], defaults=user_data)
        if created:
            if not password:
                raise serializers.ValidationError({"password": "A password is required for a new user."})
            user.set_password(password)
            user.save()
        school = validated_data["school"]
        if Membership.objects.filter(school=school, user=user).exists():
            raise serializers.ValidationError({"username": "This user already belongs to the school."})
        return Membership.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        password = validated_data.pop("password", None)
        user_data.pop("username", None)
        for key, value in user_data.items():
            setattr(instance.user, key, value)
        if password:
            instance.user.set_password(password)
        instance.user.save()
        return super().update(instance, validated_data)


class PermissionGrantSerializer(SchoolOwnedSerializer):
    class Meta:
        model = PermissionGrant
        fields = ["id", "membership", "permission", "reason", "expires_at", "created_by", "created_at"]
