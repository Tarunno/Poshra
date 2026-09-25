"""What an administrator said about a listing.

A note is the whole moderation model, because the two things an administrator
needs to do are the same thing underneath: archiving a piece and asking for a
change are both "somebody looked at this and the artisan needs to know why".

Nothing is deleted. A listing referenced by a sale cannot be removed without
either taking the artisan's earnings history with it or leaving it dangling,
and work that vanishes with no reason given leaves the artisan nothing to
answer. Archiving hides a piece from the shop, keeps the record, is reversible,
and carries the sentence that explains it.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from catalog.models import Product


class NoteKind(models.TextChoices):
    CHANGE_REQUESTED = "change_requested", "Change requested"
    ARCHIVED = "archived", "Archived"
    # Putting a piece back is an administrator's to do, not the artisan's.
    # Otherwise archiving is a suggestion: anything taken out of the shop
    # could be put back by the person it was taken from.
    RESTORED = "restored", "Put back in the shop"


class ListingNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="notes")

    # The administrator who wrote it. Kept even if the account goes, because
    # the note is part of the listing's history rather than of theirs.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notes_written",
    )
    kind = models.CharField(max_length=20, choices=NoteKind.choices)
    reason = models.TextField(max_length=1000)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notes_resolved",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # The artisan's question is "is anything waiting on me", which is
            # a query for unresolved notes on their own pieces.
            models.Index(fields=["product", "resolved_at"], name="note_open_for_piece_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} on {self.product_id}"

    @property
    def is_open(self) -> bool:
        return self.resolved_at is None
