"""Catalog: who makes the work, what the work is, and what it costs.

Money is stored as an integer in the currency's minor unit (paisa for BDT,
cents for USD) plus an ISO 4217 code. Floats cannot represent 0.1 exactly, and
rounding drift in a marketplace means someone is underpaid.
"""

import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


class Division(models.TextChoices):
    """Bangladesh's administrative divisions, where a craft's origin sits."""

    BARISHAL = "barishal", "Barishal"
    CHATTOGRAM = "chattogram", "Chattogram"
    DHAKA = "dhaka", "Dhaka"
    KHULNA = "khulna", "Khulna"
    MYMENSINGH = "mymensingh", "Mymensingh"
    RAJSHAHI = "rajshahi", "Rajshahi"
    RANGPUR = "rangpur", "Rangpur"
    SYLHET = "sylhet", "Sylhet"


class TimestampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Craft(TimestampedModel):
    """A craft tradition: jamdani, nakshi kantha, terracotta, and so on.

    Kept as data rather than a hard-coded list so the taxonomy can grow, and so
    each craft can carry the story a buyer needs to understand its value.
    """

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    name_bn = models.CharField(max_length=80, blank=True, help_text="Name in Bangla")
    summary = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    # Where the tradition comes from, which is not always where a seller lives.
    home_division = models.CharField(max_length=16, choices=Division.choices, blank=True)
    home_district = models.CharField(max_length=60, blank=True)

    class Meta:
        db_table = "catalog_craft"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class ArtisanProfile(TimestampedModel):
    """The maker behind the work.

    Location is a district plus optional coordinates for now. Proximity search
    ("crafts near me") will move this to a PostGIS point; the extension is
    already installed, so that is a migration rather than a rebuild.
    """

    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="artisan_profile"
    )
    display_name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    story = models.TextField(blank=True, help_text="How they learned the craft")
    division = models.CharField(max_length=16, choices=Division.choices)
    district = models.CharField(max_length=60)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    crafts = models.ManyToManyField(Craft, related_name="artisans", blank=True)
    # Set by a human after checking the work is genuinely handmade.
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "catalog_artisan_profile"
        ordering = ("display_name",)

    def __str__(self) -> str:
        return self.display_name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.display_name)[:50]
        super().save(*args, **kwargs)

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None


class ProductStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class PublishedProductManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=ProductStatus.PUBLISHED)


class Product(TimestampedModel):
    artisan = models.ForeignKey(ArtisanProfile, on_delete=models.CASCADE, related_name="products")
    craft = models.ForeignKey(Craft, on_delete=models.PROTECT, related_name="products")

    title = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    materials = models.CharField(max_length=200, blank=True)
    dimensions = models.CharField(max_length=120, blank=True)
    # Where this piece was made, which may differ from the craft's home.
    origin_district = models.CharField(max_length=60, blank=True)

    # Minor units: 850000 BDT = ৳8,500.00. Never a float.
    price_minor = models.PositiveIntegerField(help_text="Price in the currency's minor unit")
    currency = models.CharField(max_length=3, default="BDT")

    # Stock lives here until the inventory service owns it.
    stock = models.PositiveIntegerField(default=1, validators=[MinValueValidator(0)])
    lead_time_days = models.PositiveSmallIntegerField(
        default=3, validators=[MaxValueValidator(365)], help_text="Before it ships"
    )
    status = models.CharField(
        max_length=16, choices=ProductStatus.choices, default=ProductStatus.DRAFT
    )

    objects = models.Manager()
    published = PublishedProductManager()

    class Meta:
        db_table = "catalog_product"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["craft", "status"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:140] or uuid.uuid4().hex[:8]
            slug, suffix = base, 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                suffix += 1
                slug = f"{base}-{suffix}"
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def in_stock(self) -> bool:
        return self.stock > 0


class ProductImage(TimestampedModel):
    """An image of the piece.

    Only the URL is stored: object storage comes with the listing-generation
    work, and until then artisans can point at an existing image.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    url = models.URLField(max_length=500)
    alt_text = models.CharField(max_length=200, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "catalog_product_image"
        ordering = ("position", "created_at")

    def __str__(self) -> str:
        return f"image of {self.product_id}"
