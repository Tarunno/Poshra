"""Catalog API.

Read endpoints are public: the storefront and, later, AI agents browse without
credentials. Writes belong to the artisan who owns the listing.
"""

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import connection
from django.db.models import Count, Max, Min, Q, QuerySet
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
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

# Sort options mapped to fixed ordering expressions. User input never reaches
# order_by directly, which would let a caller order by any column.
SORT_OPTIONS = {
    "newest": ("-created_at",),
    "price_asc": ("price_minor", "-created_at"),
    "price_desc": ("-price_minor", "-created_at"),
}


def search_products(queryset: QuerySet[Product], query: str) -> QuerySet[Product]:
    """Full-text search on Postgres, ILIKE elsewhere (the SQLite test suite).

    Ranking puts title matches above description matches, which is what a
    shopper expects. Trigram and semantic search come later.
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


def filter_products(
    queryset: QuerySet[Product],
    params,
    *,
    skip: str | None = None,
) -> QuerySet[Product]:
    """Apply storefront filters.

    `skip` leaves one filter out, which is what facet counts need: the craft
    counts must ignore the selected craft, or every other craft would read zero.
    """

    def value(name: str) -> str | None:
        if name == skip:
            return None
        raw = params.get(name)
        return raw or None

    # Used by checkout to price a cart: several ids in one round trip rather
    # than one request per line item.
    if ids := value("ids"):
        wanted = [part for part in ids.split(",") if part.strip()][:100]
        queryset = queryset.filter(id__in=wanted)

    if craft := value("craft"):
        queryset = queryset.filter(craft__slug=craft)
    if artisan := value("artisan"):
        queryset = queryset.filter(artisan__slug=artisan)
    if division := value("division"):
        queryset = queryset.filter(artisan__division=division)
    if value("in_stock") == "true":
        queryset = queryset.filter(stock__gt=0)

    for name, lookup in (("min_price", "price_minor__gte"), ("max_price", "price_minor__lte")):
        raw = value(name)
        if raw and raw.isdigit():
            queryset = queryset.filter(**{lookup: int(raw)})

    if query := (value("q") or "").strip():
        queryset = search_products(queryset, query)

    return queryset


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

    def visible_products(self) -> QuerySet[Product]:
        """Published work, plus the caller's own drafts."""
        # select_related/prefetch_related keep a list of N products at a
        # constant number of queries instead of N+1.
        queryset = Product.objects.select_related("artisan", "craft").prefetch_related("images")

        user = current_user(self.request)
        if user is not None and user.role == "admin":
            return queryset

        visible = Q(status=ProductStatus.PUBLISHED)
        if user is not None:
            visible |= Q(artisan__user_id=user.id)
        return queryset.filter(visible)

    def get_queryset(self) -> QuerySet[Product]:
        if self.action not in ("list", "retrieve", "facets"):
            # Writes are authorised per object; they must not be filtered by
            # the storefront's query parameters.
            return Product.objects.select_related("artisan", "craft")

        params = self.request.query_params
        queryset = filter_products(self.visible_products(), params)

        # An artisan's own listings, drafts included. Deliberately not part of
        # filter_products: that shapes the public storefront, while this
        # depends on who is asking and so must never be served from a shared
        # cache.
        if params.get("mine") == "true":
            user = current_user(self.request)
            queryset = queryset.filter(artisan__user_id=user.id) if user else queryset.none()

        sort = params.get("sort")
        searched = bool(params.get("q", "").strip())
        # Relevance wins when the visitor searched; otherwise honour the sort.
        if sort in SORT_OPTIONS and not searched:
            queryset = queryset.order_by(*SORT_OPTIONS[sort])

        return queryset

    @action(detail=False, methods=["get"])
    def facets(self, request: Request) -> Response:
        """Counts for the filter sidebar.

        Each facet is counted with the *other* filters applied but itself
        excluded, so choosing a craft still shows how many pieces each division
        holds. Counting a facet against itself would report zero everywhere else.
        """
        params = request.query_params
        visible = self.visible_products()

        crafts = (
            filter_products(visible, params, skip="craft")
            .values("craft__slug", "craft__name", "craft__name_bn")
            .annotate(count=Count("id"))
            .order_by("-count", "craft__name")
        )
        divisions = (
            filter_products(visible, params, skip="division")
            .values("artisan__division")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        matched = filter_products(visible, params)
        price = matched.aggregate(min=Min("price_minor"), max=Max("price_minor"))

        return Response(
            {
                "crafts": [
                    {
                        "slug": row["craft__slug"],
                        "name": row["craft__name"],
                        "name_bn": row["craft__name_bn"],
                        "count": row["count"],
                    }
                    for row in crafts
                ],
                "divisions": [
                    {"value": row["artisan__division"], "count": row["count"]}
                    for row in divisions
                    if row["artisan__division"]
                ],
                "price": {"min": price["min"] or 0, "max": price["max"] or 0},
                "total": matched.count(),
                "in_stock": filter_products(visible, params, skip="in_stock")
                .filter(stock__gt=0)
                .count(),
            }
        )

    def perform_create(self, serializer) -> None:
        serializer.save(artisan=self._artisan_profile())

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
