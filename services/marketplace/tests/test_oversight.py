"""The marketplace seen from above, and who is allowed to see it.

Two kinds of assertion here. The ordinary kind, that the numbers are the
numbers. And the kind worth more: that an artisan cannot read this, because a
screen showing every artisan's work is exactly the screen somebody will try
to reach by changing a role check that was never written.
"""

import pytest
from django.utils import timezone

from accounts.models import Role, User
from catalog.models import ArtisanProfile, Craft, Division, Product, ProductStatus
from sales.models import SaleLine

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-battery-staple"
OVERVIEW = "/oversight/overview"
LISTINGS = "/oversight/listings"


@pytest.fixture
def craft(db):
    return Craft.objects.create(slug="jute-craft", name="Jute craft", name_bn="পাটজাত")


def person(email: str, role: str) -> User:
    return User.objects.create_user(email=email, password=PASSWORD, role=role)


@pytest.fixture
def admin(db):
    return person("watch@poshra.test", Role.ADMIN)


@pytest.fixture
def nasima(db):
    return ArtisanProfile.objects.create(
        user=person("nasima@poshra.test", Role.ARTISAN),
        display_name="Nasima Khatun",
        division=Division.SYLHET,
        district="Sylhet",
    )


@pytest.fixture
def karim(db):
    return ArtisanProfile.objects.create(
        user=person("karim@poshra.test", Role.ARTISAN),
        display_name="Karim Mia",
        division=Division.DHAKA,
        district="Dhamrai",
    )


def listing(artisan, craft, title, **overrides):
    return Product.objects.create(
        artisan=artisan,
        craft=craft,
        title=title,
        price_minor=430000,
        currency="BDT",
        stock=overrides.pop("stock", 3),
        status=overrides.pop("status", ProductStatus.PUBLISHED),
        **overrides,
    )


def as_person(client, user, path, **params):
    return client.get(path, params, HTTP_X_USER_ID=str(user.id))


# --- who may look -------------------------------------------------------------


def test_a_signed_out_visitor_sees_nothing(client):
    assert client.get(OVERVIEW).status_code == 403
    assert client.get(LISTINGS).status_code == 403


def test_an_artisan_cannot_read_the_whole_marketplace(client, nasima, craft):
    listing(nasima, craft, "Jute floor mat")

    # An artisan reading every other artisan's work is the thing this endpoint
    # would be if the role check were ever dropped.
    assert as_person(client, nasima.user, LISTINGS).status_code == 403
    assert as_person(client, nasima.user, OVERVIEW).status_code == 403


def test_the_role_comes_from_the_record_not_the_header(client, nasima, craft):
    # The gateway sets X-User-Role from the token. If this endpoint trusted it,
    # a role changed after the token was issued would be obeyed anyway — in
    # whichever direction happened to be wrong.
    response = client.get(LISTINGS, HTTP_X_USER_ID=str(nasima.user.id), HTTP_X_USER_ROLE="admin")
    assert response.status_code == 403


# --- what it shows ------------------------------------------------------------


def test_an_admin_sees_every_artisan(client, admin, nasima, karim, craft):
    listing(nasima, craft, "Jute floor mat")
    listing(karim, craft, "Terracotta jar")

    body = as_person(client, admin, LISTINGS).json()

    assert {row["artisan"] for row in body["results"]} == {"Nasima Khatun", "Karim Mia"}


def test_listings_can_be_narrowed_to_one_workshop(client, admin, nasima, karim, craft):
    listing(nasima, craft, "Jute floor mat")
    listing(karim, craft, "Terracotta jar")

    body = as_person(client, admin, LISTINGS, artisan=karim.slug).json()

    assert [row["title"] for row in body["results"]] == ["Terracotta jar"]


def test_the_listings_without_photographs_can_be_found(client, admin, nasima, craft):
    listing(nasima, craft, "No photograph")

    body = as_person(client, admin, LISTINGS, needs_photos="true").json()

    # The one quality check worth a filter: a listing with no photograph sells
    # nothing, and that is nobody's fault but the shop's.
    assert [row["title"] for row in body["results"]] == ["No photograph"]
    assert body["results"][0]["photographs"] == 0


def test_the_overview_counts_what_is_actionable(client, admin, nasima, craft):
    listing(nasima, craft, "Published, in stock")
    listing(nasima, craft, "Sold out", stock=0)
    listing(nasima, craft, "Still a draft", status=ProductStatus.DRAFT)

    body = as_person(client, admin, OVERVIEW).json()

    assert body["listings"]["total"] == 3
    assert body["listings"]["published"] == 2
    assert body["listings"]["draft"] == 1
    # Published with nothing to sell is a shop window with a gap in it.
    assert body["listings"]["out_of_stock"] == 1
    assert body["people"]["artisans"] == 1


def test_takings_are_counted_in_minor_units(client, admin, nasima, craft):
    piece = listing(nasima, craft, "Jute floor mat")
    SaleLine.objects.create(
        order_id="11111111-1111-1111-1111-111111111111",
        sku_id=piece.id,
        product=piece,
        artisan=nasima,
        title=piece.title,
        quantity=2,
        unit_minor=430000,
        line_minor=860000,
        currency="BDT",
        occurred_at=timezone.now(),
    )

    body = as_person(client, admin, OVERVIEW).json()

    assert body["sales"]["orders"] == 1
    assert body["sales"]["pieces"] == 2
    # Exact, not nearly right: a float here makes a day's takings an opinion.
    assert body["sales"]["takings_minor"] == 860000
    assert body["latest_sales"][0]["artisan"] == "Nasima Khatun"


# --- what an administrator may change -----------------------------------------


def note_on(client, user, piece, kind="change_requested", reason="The photograph is blurry."):
    return client.post(
        f"/oversight/listings/{piece.id}/notes",
        {"kind": kind, "reason": reason},
        content_type="application/json",
        HTTP_X_USER_ID=str(user.id),
    )


def test_archiving_takes_a_piece_out_of_the_shop_without_deleting_it(client, admin, nasima, craft):
    piece = listing(nasima, craft, "Blurry photograph")

    response = note_on(client, admin, piece, kind="archived", reason="Photograph is unusable.")

    assert response.status_code == 201
    piece.refresh_from_db()
    assert piece.status == ProductStatus.ARCHIVED
    # Still there: a piece referenced by a sale cannot be removed without
    # taking the artisan's earnings history with it, and archiving is
    # reversible where a delete is not.
    assert Product.objects.filter(id=piece.id).exists()


def test_a_note_must_say_why(client, admin, nasima, craft):
    piece = listing(nasima, craft, "Jute floor mat")

    response = note_on(client, admin, piece, kind="archived", reason="")

    # Work taken away with no explanation leaves the artisan nothing to answer.
    assert response.status_code == 400
    piece.refresh_from_db()
    assert piece.status == ProductStatus.PUBLISHED


def test_an_artisan_cannot_write_notes_on_anybody(client, nasima, karim, craft):
    piece = listing(karim, craft, "Terracotta jar")

    assert note_on(client, nasima.user, piece).status_code == 403


def test_the_artisan_sees_what_was_asked_of_them(client, admin, nasima, karim, craft):
    mine = listing(nasima, craft, "Jute floor mat")
    theirs = listing(karim, craft, "Terracotta jar")
    note_on(client, admin, mine, reason="Please add the dimensions.")
    note_on(client, admin, theirs, reason="Not yours to see.")

    body = client.get("/my/notes", HTTP_X_USER_ID=str(nasima.user.id)).json()

    assert [note["reason"] for note in body] == ["Please add the dimensions."]
    assert body[0]["listing"] == "Jute floor mat"
    assert body[0]["is_open"] is True


def test_an_artisan_can_close_a_note_on_their_own_piece(client, admin, nasima, craft):
    piece = listing(nasima, craft, "Jute floor mat")
    note_id = note_on(client, admin, piece).json()["id"]

    closed = client.post(f"/oversight/notes/{note_id}/resolve", HTTP_X_USER_ID=str(nasima.user.id))

    assert closed.status_code == 200
    assert closed.json()["is_open"] is False
    # And it leaves their list, which is the point of the list.
    assert client.get("/my/notes", HTTP_X_USER_ID=str(nasima.user.id)).json() == []


def test_somebody_elses_note_is_not_yours_to_close(client, admin, nasima, karim, craft):
    piece = listing(nasima, craft, "Jute floor mat")
    note_id = note_on(client, admin, piece).json()["id"]

    refused = client.post(f"/oversight/notes/{note_id}/resolve", HTTP_X_USER_ID=str(karim.user.id))

    # A role alone is not authorisation: this checks the note's owner.
    assert refused.status_code == 403


def test_the_overview_counts_what_is_waiting_on_somebody(client, admin, nasima, craft):
    piece = listing(nasima, craft, "Jute floor mat")
    note_on(client, admin, piece)

    body = as_person(client, admin, OVERVIEW).json()

    assert body["open_notes"] == 1
    # A day with no sales is a zero rather than a missing row, or a chart
    # slopes upward through a quiet week.
    assert len(body["daily"]) == body["window_days"] + 1
    assert body["daily"][0]["takings_minor"] == 0


def test_putting_a_piece_back_closes_the_note_that_took_it_out(client, admin, nasima, craft):
    piece = listing(nasima, craft, "Jute floor mat")
    note_on(client, admin, piece, kind="archived", reason="Photograph is unusable.")

    back = note_on(client, admin, piece, kind="restored", reason="New photograph is fine.")

    assert back.status_code == 201
    piece.refresh_from_db()
    assert piece.status == ProductStatus.PUBLISHED
    # The reason it was taken out no longer stands, so it stops being
    # something the artisan is being asked about — and being told the piece is
    # back is not itself a task.
    assert client.get("/my/notes", HTTP_X_USER_ID=str(nasima.user.id)).json() == []
    # It is still in the history, which is where a record belongs.
    history = client.get("/my/notes?open=false", HTTP_X_USER_ID=str(nasima.user.id)).json()
    assert sorted(note["kind"] for note in history) == ["archived", "restored"]


def test_an_artisan_cannot_put_their_own_piece_back(client, admin, nasima, craft):
    piece = listing(nasima, craft, "Jute floor mat")
    note_on(client, admin, piece, kind="archived", reason="Duplicate listing.")

    refused = note_on(client, nasima.user, piece, kind="restored", reason="I want it back.")

    # Otherwise archiving is a suggestion: anything taken out of the shop
    # could be put straight back by the person it was taken from.
    assert refused.status_code == 403
    piece.refresh_from_db()
    assert piece.status == ProductStatus.ARCHIVED


def test_the_table_says_what_is_already_being_dealt_with(client, admin, nasima, craft):
    listing(nasima, craft, "Nothing wrong with it")
    noticed = listing(nasima, craft, "Already mentioned")
    note_on(client, admin, noticed, reason="Please add the dimensions.")

    rows = {row["title"]: row for row in as_person(client, admin, LISTINGS).json()["results"]}

    # So an administrator can see what is in hand before saying it again.
    assert rows["Already mentioned"]["open_notes"] == 1
    assert rows["Nothing wrong with it"]["open_notes"] == 0
