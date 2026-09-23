import pytest

from accounts.models import Role, User
from catalog.models import ArtisanProfile, Craft, Division, Product, ProductStatus

pytestmark = pytest.mark.django_db

PRODUCTS = "/products"
PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def craft(db):
    return Craft.objects.create(slug="jamdani", name="Jamdani", name_bn="জামদানি")


@pytest.fixture
def artisan(db, craft):
    user = User.objects.create_user(email="rina@poshra.test", password=PASSWORD, role=Role.ARTISAN)
    profile = ArtisanProfile.objects.create(
        user=user,
        display_name="Rina Akter",
        division=Division.DHAKA,
        district="Narayanganj",
    )
    profile.crafts.add(craft)
    return profile


@pytest.fixture
def other_artisan(db):
    user = User.objects.create_user(email="karim@poshra.test", password=PASSWORD, role=Role.ARTISAN)
    return ArtisanProfile.objects.create(
        user=user,
        display_name="Karim Mia",
        division=Division.DHAKA,
        district="Dhamrai",
    )


@pytest.fixture
def product(db, artisan, craft):
    return Product.objects.create(
        artisan=artisan,
        craft=craft,
        title="Jamdani saree, indigo geometry",
        description="Handwoven over eleven weeks.",
        materials="Half-silk",
        price_minor=4200000,
        currency="BDT",
        stock=1,
        status=ProductStatus.PUBLISHED,
    )


def sign_in(client, email: str):
    client.post(
        "/auth/login",
        {"email": email, "password": PASSWORD},
        content_type="application/json",
    )


# --- model behaviour ---------------------------------------------------------


def test_slug_is_generated_from_the_title(product):
    assert product.slug == "jamdani-saree-indigo-geometry"


def test_duplicate_titles_get_distinct_slugs(artisan, craft, product):
    second = Product.objects.create(
        artisan=artisan, craft=craft, title=product.title, price_minor=100, stock=1
    )
    assert second.slug != product.slug


def test_price_is_stored_as_an_integer_in_minor_units(product):
    # 4_200_000 paisa = 42,000.00 BDT. No float ever touches the value.
    assert isinstance(product.price_minor, int)
    assert product.price_minor == 4_200_000


# --- browsing ---------------------------------------------------------------


def test_anyone_can_browse_published_products(client, product):
    body = client.get(PRODUCTS).json()
    assert body["count"] == 1
    listing = body["results"][0]
    assert listing["title"] == product.title
    assert listing["artisan"]["display_name"] == "Rina Akter"
    assert listing["craft"]["slug"] == "jamdani"


def test_drafts_are_hidden_from_the_public(client, artisan, craft):
    Product.objects.create(
        artisan=artisan, craft=craft, title="Unfinished", price_minor=1000, stock=1
    )
    assert client.get(PRODUCTS).json()["count"] == 0


def test_an_artisan_sees_their_own_drafts(client, artisan, craft):
    Product.objects.create(
        artisan=artisan, craft=craft, title="Unfinished", price_minor=1000, stock=1
    )
    sign_in(client, artisan.user.email)
    assert client.get(PRODUCTS).json()["count"] == 1


def test_creating_a_listing_returns_its_slug(client, artisan, craft):
    sign_in(client, artisan.user.email)

    response = client.post(
        PRODUCTS,
        {
            "title": "Brass lamp, hammered",
            "craft": craft.slug,
            "price_minor": 890000,
            "currency": "BDT",
            "stock": 2,
            "status": "draft",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    # The slug is generated from the title, so the caller has no way to know it
    # unless the response says.
    assert response.json()["slug"] == "brass-lamp-hammered"


def test_mine_returns_only_the_callers_listings(client, artisan, other_artisan, craft, product):
    Product.objects.create(
        artisan=other_artisan,
        craft=craft,
        title="Someone else's work",
        price_minor=1000,
        stock=1,
        status=ProductStatus.PUBLISHED,
    )
    sign_in(client, artisan.user.email)

    body = client.get(f"{PRODUCTS}?mine=true").json()
    assert body["count"] == 1
    assert body["results"][0]["title"] == product.title


def test_mine_includes_the_artisans_own_drafts(client, artisan, craft, product):
    Product.objects.create(
        artisan=artisan, craft=craft, title="Still on the loom", price_minor=1000, stock=1
    )
    sign_in(client, artisan.user.email)
    assert client.get(f"{PRODUCTS}?mine=true").json()["count"] == 2


def test_mine_returns_nothing_to_a_stranger(client, artisan, craft, product):
    # Without a session there is no "mine"; answering with the whole catalogue
    # would leak every artisan's drafts to anyone who guessed the parameter.
    assert client.get(f"{PRODUCTS}?mine=true").json()["count"] == 0


def test_filter_by_craft_and_price_range(client, artisan, craft, product):
    cheap = Craft.objects.create(slug="jute", name="Jute craft")
    Product.objects.create(
        artisan=artisan,
        craft=cheap,
        title="Jute market bag",
        price_minor=95000,
        stock=5,
        status=ProductStatus.PUBLISHED,
    )

    assert client.get(f"{PRODUCTS}?craft=jute").json()["count"] == 1
    assert client.get(f"{PRODUCTS}?max_price=100000").json()["count"] == 1
    assert client.get(f"{PRODUCTS}?min_price=100000").json()["count"] == 1


def test_filter_by_stock(client, artisan, craft):
    Product.objects.create(
        artisan=artisan,
        craft=craft,
        title="Sold out piece",
        price_minor=5000,
        stock=0,
        status=ProductStatus.PUBLISHED,
    )
    assert client.get(f"{PRODUCTS}?in_stock=true").json()["count"] == 0


def test_search_matches_title_and_craft(client, product):
    assert client.get(f"{PRODUCTS}?q=jamdani").json()["count"] == 1
    assert client.get(f"{PRODUCTS}?q=terracotta").json()["count"] == 0


def test_retrieve_by_slug(client, product):
    response = client.get(f"{PRODUCTS}/{product.slug}")
    assert response.status_code == 200
    assert response.json()["slug"] == product.slug


# --- writing -----------------------------------------------------------------


def payload(**overrides):
    return {
        "title": "Jamdani scarf, rose butidar",
        "description": "Light enough for summer.",
        "craft": "jamdani",
        "price_minor": 650000,
        "currency": "BDT",
        "stock": 4,
        "status": "published",
        **overrides,
    }


def test_signed_out_visitors_cannot_create_products(client, craft):
    response = client.post(PRODUCTS, payload(), content_type="application/json")
    assert response.status_code in (401, 403)
    assert Product.objects.count() == 0


def test_a_buyer_cannot_create_products(client, craft):
    User.objects.create_user(email="buyer@poshra.test", password=PASSWORD, role=Role.BUYER)
    sign_in(client, "buyer@poshra.test")
    response = client.post(PRODUCTS, payload(), content_type="application/json")
    assert response.status_code == 403


def test_an_artisan_creates_a_listing_owned_by_their_profile(client, artisan, craft):
    sign_in(client, artisan.user.email)
    response = client.post(PRODUCTS, payload(), content_type="application/json")

    assert response.status_code == 201
    created = Product.objects.get(title="Jamdani scarf, rose butidar")
    # Ownership comes from the session, never from the request body.
    assert created.artisan_id == artisan.id


def test_ownership_cannot_be_forged_through_the_body(client, artisan, other_artisan, craft):
    sign_in(client, artisan.user.email)
    client.post(
        PRODUCTS,
        payload(artisan=str(other_artisan.id)),
        content_type="application/json",
    )
    assert Product.objects.get().artisan_id == artisan.id


def test_an_artisan_cannot_edit_another_artisans_listing(client, other_artisan, product):
    sign_in(client, other_artisan.user.email)
    response = client.patch(
        f"{PRODUCTS}/{product.slug}",
        {"price_minor": 1},
        content_type="application/json",
    )
    assert response.status_code == 403
    product.refresh_from_db()
    assert product.price_minor == 4_200_000


def test_an_artisan_can_edit_their_own_listing(client, artisan, product):
    sign_in(client, artisan.user.email)
    response = client.patch(
        f"{PRODUCTS}/{product.slug}",
        {"price_minor": 3_900_000},
        content_type="application/json",
    )
    assert response.status_code == 200
    product.refresh_from_db()
    assert product.price_minor == 3_900_000


def test_price_must_be_positive(client, artisan, craft):
    sign_in(client, artisan.user.email)
    response = client.post(PRODUCTS, payload(price_minor=0), content_type="application/json")
    assert response.status_code == 400
    assert "price_minor" in response.json()


def test_currency_must_be_supported(client, artisan, craft):
    sign_in(client, artisan.user.email)
    response = client.post(PRODUCTS, payload(currency="XYZ"), content_type="application/json")
    assert response.status_code == 400


# --- supporting endpoints ----------------------------------------------------


def test_crafts_are_public(client, craft):
    body = client.get("/crafts").json()
    assert body[0]["slug"] == "jamdani"
    assert body[0]["name_bn"] == "জামদানি"


def test_artisans_are_public_and_expose_no_contact_details(client, artisan):
    body = client.get(f"/artisans/{artisan.slug}").json()
    assert body["display_name"] == "Rina Akter"
    assert "email" not in body and "user" not in body


def test_product_queries_stay_constant_as_the_catalog_grows(
    client, artisan, craft, django_assert_max_num_queries
):
    for index in range(10):
        Product.objects.create(
            artisan=artisan,
            craft=craft,
            title=f"Piece {index}",
            price_minor=1000 + index,
            stock=1,
            status=ProductStatus.PUBLISHED,
        )
    # select_related/prefetch_related keep this flat; without them each product
    # would fetch its artisan and craft separately (the N+1 problem).
    with django_assert_max_num_queries(6):
        client.get(PRODUCTS)


# --- facets and sorting ------------------------------------------------------


def test_facets_count_each_craft(client, artisan, craft, product):
    jute = Craft.objects.create(slug="jute", name="Jute craft")
    Product.objects.create(
        artisan=artisan,
        craft=jute,
        title="Jute market bag",
        price_minor=95000,
        stock=5,
        status=ProductStatus.PUBLISHED,
    )

    body = client.get(f"{PRODUCTS}/facets").json()
    counts = {row["slug"]: row["count"] for row in body["crafts"]}
    assert counts == {"jamdani": 1, "jute": 1}
    assert body["total"] == 2
    assert body["price"] == {"min": 95000, "max": 4_200_000}


def test_a_selected_craft_does_not_zero_the_other_craft_counts(client, artisan, craft, product):
    jute = Craft.objects.create(slug="jute", name="Jute craft")
    Product.objects.create(
        artisan=artisan,
        craft=jute,
        title="Jute market bag",
        price_minor=95000,
        stock=5,
        status=ProductStatus.PUBLISHED,
    )

    body = client.get(f"{PRODUCTS}/facets?craft=jamdani").json()
    counts = {row["slug"]: row["count"] for row in body["crafts"]}
    # Each craft is counted with the craft filter removed, so the sidebar still
    # tells the visitor what switching would give them.
    assert counts == {"jamdani": 1, "jute": 1}
    # Totals, however, reflect the active filter.
    assert body["total"] == 1


def test_facets_respect_other_active_filters(client, artisan, craft, product):
    jute = Craft.objects.create(slug="jute", name="Jute craft")
    Product.objects.create(
        artisan=artisan,
        craft=jute,
        title="Jute market bag",
        price_minor=95000,
        stock=0,
        status=ProductStatus.PUBLISHED,
    )

    body = client.get(f"{PRODUCTS}/facets?in_stock=true").json()
    counts = {row["slug"]: row["count"] for row in body["crafts"]}
    assert counts == {"jamdani": 1}


def test_sort_by_price(client, artisan, craft, product):
    Product.objects.create(
        artisan=artisan,
        craft=craft,
        title="Cheaper scarf",
        price_minor=650000,
        stock=2,
        status=ProductStatus.PUBLISHED,
    )

    ascending = client.get(f"{PRODUCTS}?sort=price_asc").json()["results"]
    assert [item["price_minor"] for item in ascending] == [650000, 4_200_000]

    descending = client.get(f"{PRODUCTS}?sort=price_desc").json()["results"]
    assert [item["price_minor"] for item in descending] == [4_200_000, 650000]


def test_unknown_sort_values_are_ignored(client, product):
    # A caller must not be able to order by an arbitrary column.
    response = client.get(f"{PRODUCTS}?sort=price_minor;DROP")
    assert response.status_code == 200


def test_products_can_be_fetched_by_id(client, artisan, craft, product):
    other = Product.objects.create(
        artisan=artisan,
        craft=craft,
        title="Another piece",
        price_minor=1000,
        stock=1,
        status=ProductStatus.PUBLISHED,
    )
    body = client.get(f"{PRODUCTS}?ids={product.id},{other.id}").json()
    assert body["count"] == 2

    single = client.get(f"{PRODUCTS}?ids={product.id}").json()
    assert single["count"] == 1
    assert single["results"][0]["id"] == str(product.id)


def test_unknown_ids_are_ignored_not_errors(client, product):
    body = client.get(f"{PRODUCTS}?ids={product.id},11111111-1111-1111-1111-111111111111").json()
    assert body["count"] == 1


def test_id_filter_still_hides_drafts(client, artisan, craft):
    draft = Product.objects.create(
        artisan=artisan, craft=craft, title="Draft piece", price_minor=1000, stock=1
    )
    assert client.get(f"{PRODUCTS}?ids={draft.id}").json()["count"] == 0


def test_a_draft_announces_no_sellable_stock(artisan, craft):
    from catalog.events import stock_payload

    draft = Product.objects.create(
        artisan=artisan, craft=craft, title="On the loom", price_minor=1000, stock=4
    )
    # A piece that is not in the shop cannot be bought, so inventory is told
    # zero rather than four — otherwise pulling a listing would leave stock
    # reservable behind it.
    assert stock_payload(draft)["quantity"] == 0
    assert stock_payload(draft)["sku_id"] == str(draft.id)


def test_a_published_piece_announces_its_count(artisan, craft, product):
    from catalog.events import stock_payload

    payload = stock_payload(product)
    assert payload["quantity"] == product.stock
    assert payload["status"] == "published"


def test_publishing_stock_is_skipped_without_a_broker(artisan, craft, product, settings):
    from catalog.events import publish_stock

    # Saving must never depend on Kafka being configured, or migrations and
    # tests would need a broker.
    settings.KAFKA_BROKERS = []
    publish_stock(product)  # must not raise


# --- photographs ---------------------------------------------------------------


def _png_bytes(size=(20, 20)) -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 120, 60)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_an_upload_is_decoded_and_re_encoded(tmp_path):
    from catalog.media import _normalise

    body, content_type, extension = _normalise(_png_bytes())

    # Re-encoding is what proves the bytes are really an image and drops EXIF
    # with them — a photograph carries GPS, and an artisan's home should not
    # ship with their listing.
    assert content_type == "image/jpeg"
    assert extension == "jpg"
    assert body[:2] == b"\xff\xd8"  # a real JPEG, whatever arrived


def test_a_file_that_is_not_an_image_is_refused():
    from catalog.media import UploadRejected, _normalise

    with pytest.raises(UploadRejected):
        _normalise(b"GIF89a<?php echo 'hello'; ?>")


def test_an_oversized_upload_is_refused_before_it_is_decoded():
    from catalog.media import MAX_BYTES, UploadRejected, store_image

    with pytest.raises(UploadRejected, match="under"):
        store_image(b"x" * (MAX_BYTES + 1), "image/jpeg", prefix="products/x")


def test_a_huge_photograph_is_scaled_down():
    from catalog.media import MAX_EDGE, _normalise

    body, _, _ = _normalise(_png_bytes((MAX_EDGE * 2, MAX_EDGE * 2)))

    import io

    from PIL import Image

    assert max(Image.open(io.BytesIO(body)).size) == MAX_EDGE


def test_only_the_owner_may_add_a_photograph(client, artisan, other_artisan, craft, product):
    from django.core.files.uploadedfile import SimpleUploadedFile

    sign_in(client, other_artisan.user.email)
    response = client.post(
        f"{PRODUCTS}/{product.slug}/images",
        {"file": SimpleUploadedFile("p.png", _png_bytes(), content_type="image/png")},
    )
    # A role alone is not authorisation: without the object-level check any
    # artisan could photograph any other artisan's work.
    assert response.status_code == 403


def test_a_stranger_cannot_add_a_photograph(client, artisan, craft, product):
    from django.core.files.uploadedfile import SimpleUploadedFile

    response = client.post(
        f"{PRODUCTS}/{product.slug}/images",
        {"file": SimpleUploadedFile("p.png", _png_bytes(), content_type="image/png")},
    )
    assert response.status_code in (401, 403)


def test_an_artisan_can_remove_a_photograph(client, artisan, craft, product, monkeypatch):
    from catalog import views
    from catalog.models import ProductImage

    image = ProductImage.objects.create(product=product, url="http://example.test/a.jpg")
    # The object store is not involved in the test; the row is what matters.
    monkeypatch.setattr(views, "delete_image", lambda url: None)

    sign_in(client, artisan.user.email)
    response = client.delete(f"{PRODUCTS}/{product.slug}/images/{image.id}")

    # Ids here are UUIDs; a digits-only route pattern matched nothing and
    # answered 404 for every delete.
    assert response.status_code == 204
    assert not ProductImage.objects.filter(pk=image.id).exists()


def test_another_artisan_cannot_remove_a_photograph(client, artisan, other_artisan, craft, product):
    from catalog.models import ProductImage

    image = ProductImage.objects.create(product=product, url="http://example.test/a.jpg")
    sign_in(client, other_artisan.user.email)

    assert client.delete(f"{PRODUCTS}/{product.slug}/images/{image.id}").status_code == 403
    assert ProductImage.objects.filter(pk=image.id).exists()


# --- saved pieces --------------------------------------------------------------

FAVOURITES = "/favourites"


def test_saving_a_piece_twice_is_the_same_as_once(client, artisan, craft, product):
    from catalog.models import Favourite

    sign_in(client, artisan.user.email)
    assert client.post(f"{PRODUCTS}/{product.slug}/favourite").status_code == 201
    assert client.post(f"{PRODUCTS}/{product.slug}/favourite").status_code == 201

    # The endpoint is "make it true", not "add one".
    assert Favourite.objects.count() == 1


def test_unsaving_a_piece_that_was_never_saved_is_not_an_error(client, artisan, craft, product):
    sign_in(client, artisan.user.email)
    response = client.delete(f"{PRODUCTS}/{product.slug}/favourite")
    assert response.status_code == 200
    assert response.json() == {"favourited": False}


def test_saved_pieces_are_only_your_own(client, artisan, other_artisan, craft, product):
    sign_in(client, artisan.user.email)
    client.post(f"{PRODUCTS}/{product.slug}/favourite")
    client.post("/auth/logout")

    sign_in(client, other_artisan.user.email)
    body = client.get(FAVOURITES).json()

    # Whether *you* saved something is per-person, which is why it is not a
    # field on the shared, cached product list.
    assert body["results"] == []
    assert body["slugs"] == []


def test_saved_pieces_need_a_session(client):
    assert client.get(FAVOURITES).status_code == 401


def test_saving_needs_a_session(client, artisan, craft, product):
    assert client.post(f"{PRODUCTS}/{product.slug}/favourite").status_code == 401


def test_the_saved_list_returns_the_pieces_and_their_slugs(client, artisan, craft, product):
    sign_in(client, artisan.user.email)
    client.post(f"{PRODUCTS}/{product.slug}/favourite")

    body = client.get(FAVOURITES).json()
    assert body["slugs"] == [product.slug]
    assert body["results"][0]["title"] == product.title


def test_a_buyer_can_save_a_piece(client, db, artisan, craft, product):
    # The viewset refuses writes from anyone who is not an artisan, which is
    # right for listings and wrong for this: saving is what buyers do.
    User.objects.create_user(email="buyer@poshra.test", password=PASSWORD, role=Role.BUYER)
    sign_in(client, "buyer@poshra.test")

    assert client.post(f"{PRODUCTS}/{product.slug}/favourite").status_code == 201
    assert client.get(FAVOURITES).json()["slugs"] == [product.slug]


# --- searching by place --------------------------------------------------------


def test_a_piece_can_be_found_by_where_it_was_made(client, artisan, craft):
    # The product page prints "Made in Sylhet"; a catalogue that cannot find
    # Sylhet is lying by omission. Note the maker's own division is Dhaka —
    # where a piece is from and where its maker works are different things.
    Product.objects.create(
        artisan=artisan,
        craft=craft,
        title="Shitalpati mat",
        origin_district="Sylhet",
        price_minor=560000,
        stock=1,
        status=ProductStatus.PUBLISHED,
    )

    body = client.get(f"{PRODUCTS}?q=Sylhet").json()
    assert [row["title"] for row in body["results"]] == ["Shitalpati mat"]


def test_a_piece_can_be_found_by_its_maker(client, artisan, craft, product):
    body = client.get(f"{PRODUCTS}?q=Rina").json()
    assert product.title in [row["title"] for row in body["results"]]


def test_a_piece_can_be_found_by_the_makers_region(client, artisan, craft, product):
    # Narayanganj is the artisan's district, not the piece's origin.
    body = client.get(f"{PRODUCTS}?q=Narayanganj").json()
    assert product.title in [row["title"] for row in body["results"]]
