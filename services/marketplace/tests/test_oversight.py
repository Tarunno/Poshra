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
