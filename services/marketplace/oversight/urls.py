from django.urls import path

from oversight.views import Listings, Overview

urlpatterns = [
    path("oversight/overview", Overview.as_view(), name="oversight-overview"),
    path("oversight/listings", Listings.as_view(), name="oversight-listings"),
]
