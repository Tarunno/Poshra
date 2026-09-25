"""What an overview needs, and nothing more.

Deliberately thinner than the storefront's serializers. This is a table an
administrator scans, not a page a buyer reads: descriptions and photographs
would be a great deal of bytes nobody looks at, and a listing's full record is
one click away on the listing itself.
"""

from __future__ import annotations

from rest_framework import serializers

from catalog.models import Product
from sales.models import SaleLine


class OversightListingSerializer(serializers.ModelSerializer):
    artisan = serializers.CharField(source="artisan.display_name", read_only=True)
    artisan_slug = serializers.CharField(source="artisan.slug", read_only=True)
    craft = serializers.CharField(source="craft.name", read_only=True)
    photographs = serializers.IntegerField(source="images.count", read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "slug",
            "title",
            "status",
            "stock",
            "price_minor",
            "currency",
            "artisan",
            "artisan_slug",
            "craft",
            "origin_district",
            "photographs",
            "created_at",
        )


class OversightSaleSerializer(serializers.ModelSerializer):
    artisan = serializers.CharField(source="artisan.display_name", default="", read_only=True)

    class Meta:
        model = SaleLine
        fields = (
            "order_id",
            "sku_id",
            "title",
            "artisan",
            "quantity",
            "line_minor",
            "currency",
            "occurred_at",
        )
