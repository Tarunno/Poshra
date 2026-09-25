"""The marketplace seen from above.

Read-only, on purpose and for now: the view has to be right before anything
destructive is built on top of it. An administrator can see every artisan's
work and what the shop has been doing; nothing here changes a row.

What it deliberately does not offer is a way to read one buyer's history. An
administrator needs to know the shop is working, which is a question about
totals and about listings. "What did this person buy" is a different question,
it is answerable from the orders a support request already names, and a screen
that answers it for anybody is a screen that will eventually be used to.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role, User
from catalog.models import Product, ProductStatus
from oversight.permissions import IsAdmin
from oversight.serializers import OversightListingSerializer, OversightSaleSerializer
from sales.models import SaleLine

RECENT = 12
WINDOW_DAYS = 30


class Listings(generics.ListAPIView):
    """Every artisan's work, filterable, newest first."""

    permission_classes = [IsAdmin]
    serializer_class = OversightListingSerializer

    def get_queryset(self):
        listings = Product.objects.select_related("artisan", "craft").annotate(
            photographs=Count("images")
        )

        params = self.request.query_params
        if artisan := params.get("artisan", "").strip():
            listings = listings.filter(artisan__slug=artisan)
        if craft := params.get("craft", "").strip():
            listings = listings.filter(craft__slug=craft)
        if state := params.get("status", "").strip():
            listings = listings.filter(status=state)
        if search := params.get("q", "").strip():
            # Plain icontains rather than the storefront's search vector: this
            # is somebody looking for a listing they already know about, and an
            # exact substring is what they will type.
            listings = listings.filter(
                Q(title__icontains=search) | Q(artisan__display_name__icontains=search)
            )
        if params.get("needs_photos") == "true":
            # The one quality check worth a filter: a listing with no
            # photograph sells nothing and is nobody's fault but ours.
            listings = listings.filter(images__isnull=True)

        return listings.order_by("-created_at")


class Overview(APIView):
    """What the marketplace has been doing lately, in numbers and in events."""

    permission_classes = [IsAdmin]

    def get(self, request: Request) -> Response:
        since = timezone.now() - timedelta(days=WINDOW_DAYS)

        listings = Product.objects.aggregate(
            total=Count("id"),
            published=Count("id", filter=Q(status=ProductStatus.PUBLISHED)),
            draft=Count("id", filter=Q(status=ProductStatus.DRAFT)),
            archived=Count("id", filter=Q(status=ProductStatus.ARCHIVED)),
            # Counted because it is actionable, unlike most totals.
            without_photographs=Count("id", filter=Q(images__isnull=True)),
            out_of_stock=Count("id", filter=Q(stock=0, status=ProductStatus.PUBLISHED)),
        )

        recent_sales = SaleLine.objects.filter(occurred_at__gte=since).aggregate(
            orders=Count("order_id", distinct=True),
            pieces=Sum("quantity"),
            takings=Sum("line_minor"),
        )

        people = User.objects.aggregate(
            artisans=Count("id", filter=Q(role=Role.ARTISAN)),
            buyers=Count("id", filter=Q(role=Role.BUYER)),
            joined_recently=Count("id", filter=Q(date_joined__gte=since)),
        )

        return Response(
            {
                "window_days": WINDOW_DAYS,
                "listings": listings,
                "sales": {
                    "orders": recent_sales["orders"] or 0,
                    "pieces": recent_sales["pieces"] or 0,
                    # Minor units, like everywhere else: a day's takings should
                    # be exact rather than nearly right.
                    "takings_minor": recent_sales["takings"] or 0,
                },
                "people": people,
                "latest_listings": OversightListingSerializer(
                    Product.objects.select_related("artisan", "craft")
                    .annotate(photographs=Count("images"))
                    .order_by("-created_at")[:RECENT],
                    many=True,
                ).data,
                "latest_sales": OversightSaleSerializer(
                    SaleLine.objects.select_related("artisan").order_by("-occurred_at")[:RECENT],
                    many=True,
                ).data,
            },
            status=status.HTTP_200_OK,
        )
