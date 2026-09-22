"""Catalog API.

Read endpoints are public: the storefront and, later, AI agents browse without
credentials. Writes belong to the artisan who owns the listing.
"""

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import connection
from django.db.models import Q, QuerySet
from rest_framework import mixins, status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from catalog.models import ArtisanProfile, Craft, Product, ProductStatus
from catalog.permissions import ReadOnlyOrArtisanOwner, current_user
from catalog.serializers import (
    ArtisanSerializer,
    CraftSerializer,
    ProductSerializer,
    ProductWriteSerializer,
)


class CraftViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Craft.objects.all()
    serializer_class = CraftSerializer
    lookup_field = "slug"
    pagination_class = None  # a short, stable list; paging it would only annoy


class ArtisanViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = ArtisanProfile.objects.prefetch_related("crafts")
    serializer_class = ArtisanSerializer
    lookup_field = "slug"


class ProductViewSet(viewsets.ModelViewSet):
    """Products, with the filters a storefront actually needs."""

    permission_classes = [ReadOnlyOrArtisanOwner]
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProductWriteSerializer
        return ProductSerializer

    def get_queryset(self) -> QuerySet[Product]:
        # select_related/prefetch_related keep a list of N products at a
        # constant number of queries instead of N+1.
        base = Product.objects.select_related("artisan", "craft").prefetch_related("images")

        user = current_user(self.request)
        if self.action in ("list", "retrieve") and not (user and user.role == "admin"):
            # Drafts are visible only to their owner.
            visible = Q(status=ProductStatus.PUBLISHED)
            if user is not None:
                visible |= Q(artisan__user_id=user.id)
            base = base.filter(visible)

        params = self.request.query_params

        if craft := params.get("craft"):
            base = base.filter(craft__slug=craft)
        if artisan := params.get("artisan"):
            base = base.filter(artisan__slug=artisan)
        if division := params.get("division"):
            base = base.filter(artisan__division=division)
        if params.get("in_stock") == "true":
            base = base.filter(stock__gt=0)

        for name, lookup in (("min_price", "price_minor__gte"), ("max_price", "price_minor__lte")):
            raw = params.get(name)
            if raw and raw.isdigit():
                base = base.filter(**{lookup: int(raw)})

        if query := params.get("q", "").strip():
            base = self._search(base, query)

        return base

    @staticmethod
    def _search(queryset: QuerySet[Product], query: str) -> QuerySet[Product]:
        """Full-text search on Postgres, ILIKE elsewhere (the SQLite test suite).

        Ranking puts title matches above description matches, which is what a
        shopper expects. A trigram index and semantic search come later.
        """
        if connection.vendor != "postgresql":
            return queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(materials__icontains=query)
                | Q(craft__name__icontains=query)
            )

        vector = (
            SearchVector("title", weight="A")
            + SearchVector("craft__name", weight="B")
            + SearchVector("materials", weight="C")
            + SearchVector("description", weight="D")
        )
        search = SearchQuery(query, search_type="websearch")
        return (
            queryset.annotate(rank=SearchRank(vector, search))
            .filter(rank__gt=0)
            .order_by("-rank", "-created_at")
        )

    def perform_create(self, serializer) -> None:
        profile = self._artisan_profile()
        serializer.save(artisan=profile)

    def create(self, request: Request, *args, **kwargs) -> Response:
        if self._artisan_profile() is None:
            return Response(
                {"detail": "Create an artisan profile before listing work."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def _artisan_profile(self) -> ArtisanProfile | None:
        user = getattr(self.request, "poshra_user", None) or current_user(self.request)
        if user is None:
            return None
        return ArtisanProfile.objects.filter(user_id=user.id).first()
