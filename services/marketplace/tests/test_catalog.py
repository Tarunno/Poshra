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
