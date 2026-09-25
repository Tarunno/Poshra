from django.urls import path

from oversight.views import Listings, MyNotes, Notes, Overview, ResolveNote

urlpatterns = [
    path("oversight/overview", Overview.as_view(), name="oversight-overview"),
    path("oversight/listings", Listings.as_view(), name="oversight-listings"),
    path("oversight/listings/<uuid:product_id>/notes", Notes.as_view(), name="oversight-notes"),
    path("oversight/notes/<uuid:note_id>/resolve", ResolveNote.as_view(), name="oversight-resolve"),
    # The artisan's side: what has been asked of them.
    path("my/notes", MyNotes.as_view(), name="my-notes"),
]
