from rest_framework import serializers

from catalog.models import ArtisanProfile, Craft, Product, ProductImage


class CraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Craft
        fields = (
            "slug",
            "name",
            "name_bn",
            "summary",
            "description",
            "home_division",
            "home_district",
        )


class ArtisanSummarySerializer(serializers.ModelSerializer):
    """The maker as shown on a product card: enough to credit them, no more."""

    is_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = ArtisanProfile
        fields = ("slug", "display_name", "division", "district", "is_verified")


class ArtisanSerializer(ArtisanSummarySerializer):
    crafts = CraftSerializer(many=True, read_only=True)

    class Meta(ArtisanSummarySerializer.Meta):
        fields = (*ArtisanSummarySerializer.Meta.fields, "story", "crafts")


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("url", "alt_text", "position", "credit", "credit_url", "license")


class ProductSerializer(serializers.ModelSerializer):
    artisan = ArtisanSummarySerializer(read_only=True)
    craft = CraftSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "slug",
            "title",
            "description",
            "materials",
            "dimensions",
            "origin_district",
            # Price travels as minor units plus a currency code; formatting is
            # the client's job, using the viewer's locale.
            "price_minor",
            "currency",
            "stock",
            "in_stock",
            "lead_time_days",
            "status",
            "artisan",
            "craft",
            "images",
            "created_at",
        )
        read_only_fields = ("id", "slug", "created_at")


class ProductWriteSerializer(serializers.ModelSerializer):
    """What an artisan may set. `artisan` is taken from the request, never the body."""

    craft = serializers.SlugRelatedField(slug_field="slug", queryset=Craft.objects.all())

    class Meta:
        model = Product
        fields = (
            # Read-only, but returned: a create should tell the caller what it
            # made, and the slug is how everything else addresses it.
            "slug",
            "title",
            "description",
            "materials",
            "dimensions",
            "origin_district",
            "price_minor",
            "currency",
            "stock",
            "lead_time_days",
            "status",
            "craft",
        )
        read_only_fields = ("slug",)

    def validate_price_minor(self, value: int) -> int:
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate_currency(self, value: str) -> str:
        allowed = {"BDT", "USD", "EUR", "GBP"}
        if value.upper() not in allowed:
            raise serializers.ValidationError(f"Currency must be one of {sorted(allowed)}.")
        return value.upper()
