from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.views import exception_handler as drf_exception_handler


class BusinessRuleError(serializers.ValidationError):
    """A request that is well formed but breaks a school rule (e.g. editing a locked mark sheet)."""


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "error_dict") else {"detail": exc.messages}
        exc = serializers.ValidationError(detail)
    return drf_exception_handler(exc, context)
