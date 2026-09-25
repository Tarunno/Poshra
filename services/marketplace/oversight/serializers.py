"""What an overview needs, and nothing more.

Deliberately thinner than the storefront's serializers. This is a table an
administrator scans, not a page a buyer reads: descriptions and photographs
would be a great deal of bytes nobody looks at, and a listing's full record is
one click away on the listing itself.
"""

from __future__ import annotations

from rest_framework import serializers

from catalog.models import Product
from oversight.models import ListingNote, NoteKind
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


class ListingNoteSerializer(serializers.ModelSerializer):
    listing = serializers.CharField(source="product.title", read_only=True)
    listing_slug = serializers.CharField(source="product.slug", read_only=True)
    author = serializers.CharField(source="author.full_name", default="", read_only=True)
    is_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = ListingNote
        fields = (
            "id",
            "kind",
            "reason",
            "listing",
            "listing_slug",
            "author",
            "created_at",
            "resolved_at",
            "is_open",
        )


class WriteNoteSerializer(serializers.Serializer):
    """What an administrator sends. The reason is required on purpose: an
    archiving with no explanation is work taken away with nothing to answer."""

    kind = serializers.ChoiceField(choices=NoteKind.choices)
    reason = serializers.CharField(max_length=1000, min_length=4, trim_whitespace=True)
