import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    BUYER = "buyer", "Buyer"
    ARTISAN = "artisan", "Artisan"
    ADMIN = "admin", "Admin"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra):
        extra.setdefault("role", Role.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Email is the login identifier; usernames add nothing for a marketplace."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.BUYER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    # Bumped on logout-everywhere or a password change: tokens issued before
    # this moment are refused, which is how a stateless JWT gets revoked.
    tokens_valid_after = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "accounts_user"

    def __str__(self) -> str:
        return self.email

    @property
    def is_artisan(self) -> bool:
        return self.role == Role.ARTISAN


class RefreshTokenQuerySet(models.QuerySet):
    def active(self):
        return self.filter(revoked_at__isnull=True, used_at__isnull=True)


class RefreshToken(models.Model):
    """A rotating refresh token, stored hashed.

    Rotation: every refresh marks the presented token used and issues a new one
    in the same *family*. If a token that was already used turns up again, it
    was probably stolen and replayed, so the whole family is revoked and the
    user must log in again.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="refresh_tokens"
    )
    # One family per login; rotation keeps the family and replaces the token.
    family = models.UUIDField(default=uuid.uuid4, editable=False)
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = RefreshTokenQuerySet.as_manager()

    class Meta:
        db_table = "accounts_refresh_token"
        indexes = [
            models.Index(fields=["family"]),
            models.Index(fields=["user", "expires_at"]),
        ]

    def __str__(self) -> str:
        return f"refresh({self.user_id}, {self.family})"

    @property
    def is_usable(self) -> bool:
        return self.revoked_at is None and self.used_at is None and self.expires_at > timezone.now()
