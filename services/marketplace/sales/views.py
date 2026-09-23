"""Sales analytics for the artisan who made the pieces.

Every query here is scoped to the caller's own workshop. Sales are commercially
sensitive: an artisan must never be able to read another's numbers by changing
a parameter, so there is no artisan parameter to change.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.identity import current_user
from accounts.models import Role
from catalog.models import ArtisanProfile
from sales.models import SaleLine

# Long enough to show a trend, short enough to stay one screen wide.
WINDOW_DAYS = 30
TOP_PIECES = 5
RECENT_SALES = 8


class SalesSummary(APIView):
    """What this artisan sold: totals, a daily series, best pieces, latest sales."""

    permission_classes = [permissions.AllowAny]  # authorisation is by identity below

    def get(self, request: Request) -> Response:
        user = current_user(request)
        if user is None:
            return Response(
                {"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )
        if user.role not in (Role.ARTISAN, Role.ADMIN):
            return Response(
                {"detail": "Only artisans have sales."}, status=status.HTTP_403_FORBIDDEN
            )

        profile = ArtisanProfile.objects.filter(user_id=user.id).first()
        if profile is None:
            return Response(self._empty())

        sales = SaleLine.objects.filter(artisan=profile)

        since = timezone.now() - timedelta(days=WINDOW_DAYS - 1)
        windowed = sales.filter(occurred_at__gte=since)

        totals = sales.aggregate(
            revenue=Sum("line_minor"),
            pieces=Sum("quantity"),
            orders=Count("order_id", distinct=True),
        )
        currency = sales.values_list("currency", flat=True).first() or "BDT"

        return Response(
            {
                "currency": currency,
                "revenue_minor": totals["revenue"] or 0,
                "pieces_sold": totals["pieces"] or 0,
                "orders": totals["orders"] or 0,
                "window_days": WINDOW_DAYS,
                "daily": self._daily(windowed),
                "top_pieces": self._top_pieces(sales),
                "recent": self._recent(sales),
            }
        )

    @staticmethod
    def _empty() -> dict:
        today = timezone.localdate()
        return {
            "currency": "BDT",
            "revenue_minor": 0,
            "pieces_sold": 0,
            "orders": 0,
            "window_days": WINDOW_DAYS,
            "daily": [
                {
                    "date": (today - timedelta(days=offset)).isoformat(),
                    "revenue_minor": 0,
                    "pieces": 0,
                }
                for offset in range(WINDOW_DAYS - 1, -1, -1)
            ],
            "top_pieces": [],
            "recent": [],
        }

    @staticmethod
    def _daily(sales) -> list[dict]:
        """One entry per day, including the days nothing sold.

        A chart drawn only from days with sales silently rescales its own time
        axis, so a quiet week looks identical to a busy one.
        """
        rows = (
            sales.annotate(day=TruncDate("occurred_at"))
            .values("day")
            .annotate(revenue=Sum("line_minor"), pieces=Sum("quantity"))
        )
        by_day: dict[date, dict] = {row["day"]: row for row in rows}

        today = timezone.localdate()
        series = []
        for offset in range(WINDOW_DAYS - 1, -1, -1):
            day = today - timedelta(days=offset)
            row = by_day.get(day)
            series.append(
                {
                    "date": day.isoformat(),
                    "revenue_minor": row["revenue"] if row else 0,
                    "pieces": row["pieces"] if row else 0,
                }
            )
        return series

    @staticmethod
    def _top_pieces(sales) -> list[dict]:
        rows = (
            sales.values("product__slug", "title")
            .annotate(revenue=Sum("line_minor"), pieces=Sum("quantity"))
            .order_by("-revenue")[:TOP_PIECES]
        )
        return [
            {
                "slug": row["product__slug"],
                "title": row["title"],
                "pieces": row["pieces"],
                "revenue_minor": row["revenue"],
            }
            for row in rows
        ]

    @staticmethod
    def _recent(sales) -> list[dict]:
        # No buyer identity: an artisan needs to know what sold and when, not
        # who bought it.
        rows = sales.select_related("product").order_by("-occurred_at")[:RECENT_SALES]
        return [
            {
                "order_id": str(row.order_id),
                "slug": row.product.slug if row.product else None,
                "title": row.title,
                "quantity": row.quantity,
                "line_minor": row.line_minor,
                "currency": row.currency,
                "occurred_at": row.occurred_at.isoformat(),
            }
            for row in rows
        ]
