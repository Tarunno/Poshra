"""Request and response shapes for the auth API.

Validation lives here rather than in the views: it is declarative, reusable and
produces consistent error bodies.
"""

from rest_framework import serializers

from accounts.models import AgentToken, Role, User

MIN_PASSWORD_LENGTH = 12


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=MIN_PASSWORD_LENGTH, write_only=True)
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    # Only these two can be chosen; "admin" is granted, never requested.
    role = serializers.ChoiceField(choices=[Role.BUYER, Role.ARTISAN], default=Role.BUYER)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "full_name", "role")
        read_only_fields = fields


class AgentTokenSerializer(serializers.ModelSerializer):
    """A token as the shopper sees it in their settings — never its value."""

    active = serializers.BooleanField(source="is_active", read_only=True)

    class Meta:
        model = AgentToken
        fields = ("id", "label", "created_at", "expires_at", "last_used_at", "revoked_at", "active")
        read_only_fields = fields


class AgentTokenCreateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=80, trim_whitespace=True)

    def validate_label(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Give the token a name you will recognise.")
        return value.strip()
