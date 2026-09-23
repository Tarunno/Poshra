from django.urls import path
from rest_framework.routers import DefaultRouter

from catalog.views import ArtisanViewSet, CraftViewSet, FavouriteList, ProductViewSet

# No trailing slash, matching the auth endpoints: one URL style across the API.
router = DefaultRouter(trailing_slash=False)
router.register("products", ProductViewSet, basename="product")
router.register("crafts", CraftViewSet, basename="craft")
router.register("artisans", ArtisanViewSet, basename="artisan")

urlpatterns = [
    # Not a viewset route: "what have I saved" is about the person, not about
    # any one product.
    path("favourites", FavouriteList.as_view(), name="favourites"),
    *router.urls,
]
