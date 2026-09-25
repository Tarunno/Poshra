"""The marketplace seen from above, and the one thing an administrator may change.

An administrator can see every artisan's work and what the shop has been
doing. The only write is a note: archiving a piece or asking for a change,
both of which say why and both of which the artisan can see and answer.

What it deliberately does not offer is a way to read one buyer's history. An
administrator needs to know the shop is working, which is a question about
totals and about listings. "What did this person buy" is a different question,
it is answerable from the orders a support request already names, and a screen
that answers it for anybody is a screen that will eventually be used to.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.identity import current_user
from accounts.models import Role, User
from catalog.models import Product, ProductStatus
from oversight.models import ListingNote, NoteKind
from oversight.permissions import IsAdmin
from oversight.serializers import (
    ListingNoteSerializer,
    OversightListingSerializer,
    OversightSaleSerializer,
    WriteNoteSerializer,
)
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
                # Enough to draw with. A total says the shop works; a shape says
                # whether it is getting better or worse, which is the question an
                # overview is actually opened to answer.
                "daily": _daily_takings(since),
                "top_artisans": _top_artisans(since),
                "top_crafts": _top_crafts(since),
                "open_notes": ListingNote.objects.filter(resolved_at__isnull=True).count(),
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


def _daily_takings(since) -> list[dict]:
    """One row per day, including the days nothing sold.

    A chart drawn only from days with sales slopes upward through a quiet week,
    because the quiet days are simply missing rather than zero.
    """
    rows = {
        row["day"]: row
        for row in SaleLine.objects.filter(occurred_at__gte=since)
        .annotate(day=TruncDate("occurred_at"))
        .values("day")
        .annotate(takings_minor=Sum("line_minor"), pieces=Sum("quantity"))
        .order_by("day")
    }

    start = since.date()
    today = timezone.now().date()
    days = []
    while start <= today:
        row = rows.get(start)
        days.append(
            {
                "date": start.isoformat(),
                "takings_minor": row["takings_minor"] if row else 0,
                "pieces": row["pieces"] if row else 0,
            }
        )
        start += timedelta(days=1)
    return days


def _top_artisans(since) -> list[dict]:
    return list(
        SaleLine.objects.filter(occurred_at__gte=since, artisan__isnull=False)
        .values(name=F("artisan__display_name"), slug=F("artisan__slug"))
        .annotate(takings_minor=Sum("line_minor"), pieces=Sum("quantity"))
        .order_by("-takings_minor")[:5]
    )


def _top_crafts(since) -> list[dict]:
    return list(
        SaleLine.objects.filter(occurred_at__gte=since, product__isnull=False)
        .values(name=F("product__craft__name"))
        .annotate(takings_minor=Sum("line_minor"), pieces=Sum("quantity"))
        .order_by("-takings_minor")[:5]
    )


class Notes(APIView):
    """Write a note against a listing: a change request, or an archiving."""

    permission_classes = [IsAdmin]

    def post(self, request: Request, product_id) -> Response:
        listing = Product.objects.filter(id=product_id).first()
        if listing is None:
            return Response({"detail": "No such listing."}, status=status.HTTP_404_NOT_FOUND)

        form = WriteNoteSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        note = ListingNote.objects.create(
            product=listing,
            author=getattr(request, "poshra_user", None) or current_user(request),
            kind=form.validated_data["kind"],
            reason=form.validated_data["reason"],
        )

        if note.kind == NoteKind.ARCHIVED:
            # Out of the shop, not out of the database: a piece referenced by a
            # sale cannot be removed without taking the artisan's earnings
            # history with it, and this is reversible where a delete is not.
            listing.status = ProductStatus.ARCHIVED
            listing.save(update_fields=["status"])

        return Response(ListingNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class ResolveNote(APIView):
    """Mark a note answered.

    Either side may: the artisan when they have done what was asked, the
    administrator when they no longer need it. Anyone else is refused, which
    is why this checks the note's owner rather than only a role.
    """

    def post(self, request: Request, note_id) -> Response:
        user = current_user(request)
        if user is None:
            return Response({"detail": "Sign in first."}, status=status.HTTP_403_FORBIDDEN)

        note = ListingNote.objects.select_related("product__artisan").filter(id=note_id).first()
        if note is None:
            return Response({"detail": "No such note."}, status=status.HTTP_404_NOT_FOUND)

        theirs = getattr(note.product.artisan, "user_id", None) == user.id
        if not theirs and user.role != Role.ADMIN:
            return Response(
                {"detail": "This note is not yours to close."}, status=status.HTTP_403_FORBIDDEN
            )

        if note.is_open:
            note.resolved_at = timezone.now()
            note.resolved_by = user
            note.save(update_fields=["resolved_at", "resolved_by"])

        return Response(ListingNoteSerializer(note).data)


class MyNotes(generics.ListAPIView):
    """What an artisan has been asked to do."""

    serializer_class = ListingNoteSerializer
    pagination_class = None

    def get_queryset(self):
        user = current_user(self.request)
        if user is None:
            return ListingNote.objects.none()
        notes = ListingNote.objects.select_related("product").filter(
            product__artisan__user_id=user.id
        )
        if self.request.query_params.get("open") != "false":
            notes = notes.filter(resolved_at__isnull=True)
        return notes
