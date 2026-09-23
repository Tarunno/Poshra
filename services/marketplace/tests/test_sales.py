import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import Role, User
from catalog.models import ArtisanProfile, Craft, Division, Product, ProductStatus
from sales.events import UnprocessableEvent, record_order
from sales.models import SaleLine

pytestmark = pytest.mark.django_db

SUMMARY = "/sales/summary"
PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def craft(db):
    return Craft.objects.create(slug="shitalpati", name="Shitalpati", name_bn="শীতলপাটি")


@pytest.fixture
def artisan(db):
    user = User.objects.create_user(
        email="nasima@poshra.test", password=PASSWORD, role=Role.ARTISAN
    )
    return ArtisanProfile.objects.create(
        user=user, display_name="Nasima Khatun", division=Division.SYLHET, district="Sylhet"
    )


@pytest.fixture
def other_artisan(db):
    user = User.objects.create_user(email="karim@poshra.test", password=PASSWORD, role=Role.ARTISAN)
    return ArtisanProfile.objects.create(
        user=user, display_name="Karim Mia", division=Division.DHAKA, district="Dhamrai"
    )


def make_product(artisan, craft, title="Shitalpati mat", price=560000):
    return Product.objects.create(
        artisan=artisan,
        craft=craft,
        title=title,
        price_minor=price,
        currency="BDT",
        stock=5,
        status=ProductStatus.PUBLISHED,
    )


def order_event(product, *, quantity=2, order_id=None, when=None):
    return {
        "event_id": str(uuid.uuid4()),
        "order_id": order_id or str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "occurred_at": (when or timezone.now()).isoformat(),
        "currency": "BDT",
        "total_minor": product.price_minor * quantity,
        "items": [
            {
                "sku_id": str(product.id),
                "quantity": quantity,
                "unit_minor": product.price_minor,
                "title": product.title,
                "artisan_name": product.artisan.display_name,
            }
        ],
    }


def sign_in(client, email: str):
    client.post(
        "/auth/login",
        {"email": email, "password": PASSWORD},
        content_type="application/json",
    )


def test_an_order_event_becomes_a_sale_for_the_maker(artisan, craft):
    product = make_product(artisan, craft)

    record_order(order_event(product))

    sale = SaleLine.objects.get()
    # The event names a sku, not a maker. Resolving it is the whole reason this
    # read model lives in the service that owns the products.
    assert sale.artisan == artisan
    assert sale.product == product
    assert sale.quantity == 2
    assert sale.line_minor == product.price_minor * 2


def test_replaying_the_same_event_does_not_double_count(artisan, craft):
    product = make_product(artisan, craft)
    event = order_event(product)

    record_order(event)
    record_order(event)

    # Delivery is at-least-once, so this is not a hypothetical.
    assert SaleLine.objects.count() == 1
    assert SaleLine.objects.get().quantity == 2


def test_a_sale_keeps_the_price_it_was_sold_at(artisan, craft):
    product = make_product(artisan, craft, price=560000)
    record_order(order_event(product, quantity=1))

    product.title = "Shitalpati mat, renamed"
    product.price_minor = 999000
    product.save()

    sale = SaleLine.objects.get()
    # A sale is a fact about a moment; repricing the listing must not rewrite
    # what was earned last week.
    assert sale.unit_minor == 560000
    assert sale.title == "Shitalpati mat"


def test_an_event_without_items_is_rejected(artisan, craft):
    with pytest.raises(UnprocessableEvent):
        record_order({"order_id": str(uuid.uuid4()), "occurred_at": timezone.now().isoformat()})


def test_summary_counts_only_the_callers_own_sales(client, artisan, other_artisan, craft):
    mine = make_product(artisan, craft, title="Mine", price=100000)
    theirs = make_product(other_artisan, craft, title="Theirs", price=500000)
    record_order(order_event(mine, quantity=3))
    record_order(order_event(theirs, quantity=1))

    sign_in(client, artisan.user.email)
    body = client.get(SUMMARY).json()

    assert body["revenue_minor"] == 300000
    assert body["pieces_sold"] == 3
    assert body["orders"] == 1
    assert [piece["title"] for piece in body["top_pieces"]] == ["Mine"]


def test_summary_needs_a_session(client):
    assert client.get(SUMMARY).status_code == 401


def test_summary_is_refused_to_buyers(client, db):
    User.objects.create_user(email="buyer@poshra.test", password=PASSWORD, role=Role.BUYER)
    sign_in(client, "buyer@poshra.test")
    assert client.get(SUMMARY).status_code == 403


def test_the_daily_series_includes_quiet_days(client, artisan, craft):
    product = make_product(artisan, craft)
    record_order(order_event(product, when=timezone.now() - timedelta(days=3)))

    sign_in(client, artisan.user.email)
    daily = client.get(SUMMARY).json()["daily"]

    # A chart drawn only from days with sales rescales its own axis, so a quiet
    # week would look exactly like a busy one.
    assert len(daily) == 30
    assert sum(day["revenue_minor"] for day in daily) == product.price_minor * 2
    assert daily[0]["date"] < daily[-1]["date"]


def test_recent_sales_do_not_name_the_buyer(client, artisan, craft):
    product = make_product(artisan, craft)
    record_order(order_event(product))

    sign_in(client, artisan.user.email)
    recent = client.get(SUMMARY).json()["recent"]

    assert len(recent) == 1
    assert "user_id" not in recent[0] and "buyer" not in recent[0]
