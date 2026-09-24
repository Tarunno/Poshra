"""The repair path: the catalog's count read back from the ledger that owns it."""

import contextlib
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from accounts.models import Role, User
from catalog.inventory_client import InventoryUnavailable
from catalog.models import ArtisanProfile, Craft, Division, Product, ProductStatus

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def artisan(db):
    user = User.objects.create_user(
        email="nasima@poshra.test", password=PASSWORD, role=Role.ARTISAN
    )
    return ArtisanProfile.objects.create(
        user=user, display_name="Nasima Khatun", division=Division.SYLHET, district="Sylhet"
    )


@pytest.fixture
def craft(db):
    return Craft.objects.create(slug="jute", name="Jute craft", name_bn="পাটজাত")


def make_product(artisan, craft, *, stock, title="Jute floor mat"):
    return Product.objects.create(
        artisan=artisan,
        craft=craft,
        title=title,
        price_minor=430000,
        currency="BDT",
        stock=stock,
        status=ProductStatus.PUBLISHED,
    )


def run(monkeypatch, ledger, **options) -> str:
    """Run the command against a ledger given as {sku_id: on-hand}."""
    from catalog.management.commands import reconcile_stock

    @contextlib.contextmanager
    def fake_channel():
        yield object()

    monkeypatch.setattr(reconcile_stock, "channel", fake_channel)
    monkeypatch.setattr(reconcile_stock, "on_hand", lambda stub, sku_ids, **kw: {
        sku: ledger[sku] for sku in sku_ids if sku in ledger
    })

    out = StringIO()
    call_command("reconcile_stock", stdout=out, **options)
    return out.getvalue()


def test_the_ledger_wins(monkeypatch, artisan, craft):
    product = make_product(artisan, craft, stock=5)

    run(monkeypatch, {str(product.id): 3})

    product.refresh_from_db()
    # The drift this exists to repair: sold twice, never decremented here.
    assert product.stock == 3


def test_a_dry_run_reports_without_writing(monkeypatch, artisan, craft):
    product = make_product(artisan, craft, stock=5)

    output = run(monkeypatch, {str(product.id): 3}, dry_run=True)

    product.refresh_from_db()
    assert product.stock == 5
    assert "5 -> 3" in output
    assert "would correct 1" in output


def test_a_listing_already_in_step_is_left_alone(monkeypatch, artisan, craft):
    product = make_product(artisan, craft, stock=4)

    output = run(monkeypatch, {str(product.id): 4})

    assert "corrected 0" in output


def test_a_sku_the_ledger_never_heard_of_is_not_zeroed(monkeypatch, artisan, craft):
    # A listing created while the broker was down: its level was never
    # announced. Writing zero here would take a real piece off the shop.
    product = make_product(artisan, craft, stock=2)

    output = run(monkeypatch, {})

    product.refresh_from_db()
    assert product.stock == 2
    assert "1 not in the ledger" in output


def test_batches_span_the_whole_catalogue(monkeypatch, artisan, craft):
    first = make_product(artisan, craft, stock=5, title="One")
    second = make_product(artisan, craft, stock=5, title="Two")
    third = make_product(artisan, craft, stock=5, title="Three")

    # Three listings, two per call: the second batch must not be forgotten.
    run(monkeypatch, {str(first.id): 1, str(second.id): 2, str(third.id): 3}, batch_size=2)

    first.refresh_from_db()
    second.refresh_from_db()
    third.refresh_from_db()
    assert (first.stock, second.stock, third.stock) == (1, 2, 3)


def test_an_unreachable_ledger_stops_the_run(monkeypatch, artisan, craft):
    from catalog.management.commands import reconcile_stock

    @contextlib.contextmanager
    def fake_channel():
        raise InventoryUnavailable("INVENTORY_ADDR is not set")
        yield  # pragma: no cover

    monkeypatch.setattr(reconcile_stock, "channel", fake_channel)
    make_product(artisan, craft, stock=5)

    # Half a repair is worse than none.
    with pytest.raises(CommandError, match="INVENTORY_ADDR"):
        call_command("reconcile_stock", stdout=StringIO())
