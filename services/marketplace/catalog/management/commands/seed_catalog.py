"""Seed the catalog with real crafts, makers and pieces.

Demo data, but not lorem ipsum: the crafts, districts and price ranges are
real, so the storefront can be judged on how it actually reads.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User
from catalog.models import ArtisanProfile, Craft, Division, Product, ProductStatus

CRAFTS = [
    {
        "slug": "jamdani",
        "name": "Jamdani",
        "name_bn": "জামদানি",
        "summary": "Handwoven muslin with motifs added thread by thread on the loom.",
        "description": (
            "Jamdani is woven on a handloom where each motif is inserted by hand with a fine "
            "bamboo needle, thread over thread, without any mechanical pattern. A single saree "
            "can take two weavers several months. Recognised by UNESCO as intangible cultural "
            "heritage."
        ),
        "home_division": Division.DHAKA,
        "home_district": "Narayanganj",
    },
    {
        "slug": "nakshi-kantha",
        "name": "Nakshi Kantha",
        "name_bn": "নকশি কাঁথা",
        "summary": "Layered cloth quilted with a running stitch into pictures and patterns.",
        "description": (
            "Old saris are layered and joined with a simple running stitch, then covered in "
            "figures: fish, lotuses, village scenes. Traditionally made at home from worn cloth, "
            "which is why no two are the same."
        ),
        "home_division": Division.MYMENSINGH,
        "home_district": "Jamalpur",
    },
    {
        "slug": "terracotta",
        "name": "Terracotta",
        "name_bn": "পোড়ামাটি",
        "summary": "Clay shaped on a wheel or by hand, then fired to a deep red.",
        "description": (
            "Potters work river clay into vessels, plaques and figures, then fire them in "
            "open kilns. The temple panels of Bengal are the same craft at architectural scale."
        ),
        "home_division": Division.DHAKA,
        "home_district": "Dhamrai",
    },
    {
        "slug": "jute",
        "name": "Jute craft",
        "name_bn": "পাটজাত পণ্য",
        "summary": "Bags, mats and baskets woven from the golden fibre.",
        "description": (
            "Jute grows across the delta and is spun and woven into hard-wearing goods. "
            "Biodegradable, strong, and the country's signature fibre."
        ),
        "home_division": Division.KHULNA,
        "home_district": "Faridpur",
    },
    {
        "slug": "shitalpati",
        "name": "Shitalpati",
        "name_bn": "শীতল পাটি",
        "summary": "Cool sleeping mats woven from murta cane.",
        "description": (
            "Strips of murta cane are split fine and woven into mats that stay cool in heat. "
            "The weaving of Shitalpati is on UNESCO's intangible heritage list."
        ),
        "home_division": Division.SYLHET,
        "home_district": "Sylhet",
    },
    {
        "slug": "brass",
        "name": "Brass and bell metal",
        "name_bn": "কাঁসা ও পিতল",
        "summary": "Cast and beaten metalware for the table and the shrine.",
        "description": (
            "Bell metal and brass are cast, beaten and polished into bowls, plates and lamps. "
            "Dhamrai has worked metal this way for centuries."
        ),
        "home_division": Division.DHAKA,
        "home_district": "Dhamrai",
    },
]

ARTISANS = [
    {
        "email": "rina.weaver@poshra.test",
        "display_name": "Rina Akter",
        "division": Division.DHAKA,
        "district": "Narayanganj",
        "latitude": 23.7500,
        "longitude": 90.5000,
        "story": (
            "Third-generation jamdani weaver in Rupganj. Learned at her mother's loom at twelve, "
            "and now works a two-person loom with her husband."
        ),
        "crafts": ["jamdani"],
        "verified": True,
    },
    {
        "email": "shefali.kantha@poshra.test",
        "display_name": "Shefali Begum",
        "division": Division.MYMENSINGH,
        "district": "Jamalpur",
        "latitude": 24.9375,
        "longitude": 89.9375,
        "story": (
            "Stitches nakshi kantha with a women's collective of nineteen, working from the "
            "motifs her grandmother used."
        ),
        "crafts": ["nakshi-kantha"],
        "verified": True,
    },
    {
        "email": "karim.potter@poshra.test",
        "display_name": "Karim Mia",
        "division": Division.DHAKA,
        "district": "Dhamrai",
        "latitude": 23.9167,
        "longitude": 90.2167,
        "story": "Throws terracotta and casts bell metal in a workshop his father built in 1978.",
        "crafts": ["terracotta", "brass"],
        "verified": True,
    },
    {
        "email": "nasima.jute@poshra.test",
        "display_name": "Nasima Khatun",
        "division": Division.KHULNA,
        "district": "Faridpur",
        "latitude": 23.6070,
        "longitude": 89.8429,
        "story": "Weaves jute into bags and floor mats, dyeing the fibre with local pigments.",
        "crafts": ["jute", "shitalpati"],
        "verified": False,
    },
]

# price_minor is in paisa: 100 paisa = 1 BDT.
PRODUCTS = [
    (
        "rina.weaver@poshra.test",
        "jamdani",
        "Jamdani saree, white with indigo geometry",
        "Half-silk jamdani woven over eleven weeks. The motif repeats in indigo "
        "across an unbleached ground, each one inserted by hand at the loom.",
        "Half-silk (cotton weft, silk warp)",
        "5.5m x 1.1m",
        4200000,
        1,
        14,
        "Narayanganj",
    ),
    (
        "rina.weaver@poshra.test",
        "jamdani",
        "Jamdani scarf, rose butidar",
        "A narrow jamdani in the butidar style: small scattered motifs across a rose ground. "
        "Light enough for summer, worked on the same loom as the sarees.",
        "Cotton",
        "1.8m x 0.5m",
        650000,
        4,
        7,
        "Narayanganj",
    ),
    (
        "shefali.kantha@poshra.test",
        "nakshi-kantha",
        "Nakshi kantha throw, fish and lotus",
        "Six layers of old cotton sari joined with running stitch, then covered in fish, lotuses "
        "and a border of vines. Roughly four months of evening work.",
        "Reclaimed cotton sari, cotton thread",
        "2.1m x 1.4m",
        1850000,
        1,
        10,
        "Jamalpur",
    ),
    (
        "shefali.kantha@poshra.test",
        "nakshi-kantha",
        "Kantha cushion covers, pair",
        "Two covers stitched from the same cloth, with a simple running-stitch grid and a knot at "
        "each corner.",
        "Reclaimed cotton",
        "45cm x 45cm each",
        320000,
        6,
        5,
        "Jamalpur",
    ),
    (
        "shefali.kantha@poshra.test",
        "nakshi-kantha",
        "Embroidered kantha wall hanging",
        "A village scene in running stitch: boats on the river, a banyan, birds overhead.",
        "Cotton, cotton thread",
        "90cm x 60cm",
        540000,
        2,
        7,
        "Jamalpur",
    ),
    (
        "karim.potter@poshra.test",
        "terracotta",
        "Terracotta water jar with painted bands",
        "Thrown on a kick wheel and fired in an open kiln, with slip-painted "
        "bands around the belly.",
        "River clay",
        "H 34cm, D 28cm",
        210000,
        5,
        4,
        "Dhamrai",
    ),
    (
        "karim.potter@poshra.test",
        "terracotta",
        "Terracotta temple plaque, dancing figure",
        "A relief panel in the style of Bengal's terracotta temples, pressed "
        "from a hand-carved mould.",
        "River clay",
        "30cm x 20cm",
        380000,
        3,
        6,
        "Dhamrai",
    ),
    (
        "karim.potter@poshra.test",
        "brass",
        "Bell metal serving bowl",
        "Cast, beaten and polished by hand. Bell metal rings when struck, which is how it earned "
        "the name.",
        "Bell metal (kansa)",
        "D 22cm",
        720000,
        2,
        8,
        "Dhamrai",
    ),
    (
        "karim.potter@poshra.test",
        "brass",
        "Brass oil lamp, five wicks",
        "A standing lamp with five wick arms, used at festivals and in household shrines.",
        "Brass",
        "H 40cm",
        890000,
        1,
        10,
        "Dhamrai",
    ),
    (
        "nasima.jute@poshra.test",
        "jute",
        "Jute market bag, natural",
        "A flat-bottomed bag woven from undyed jute with a reinforced handle. Holds a week of "
        "vegetables.",
        "Jute",
        "38cm x 36cm x 12cm",
        95000,
        12,
        3,
        "Faridpur",
    ),
    (
        "nasima.jute@poshra.test",
        "jute",
        "Jute floor mat, indigo stripe",
        "Handwoven mat with an indigo stripe at each end, dyed before weaving.",
        "Jute, natural dye",
        "1.8m x 1.2m",
        430000,
        3,
        6,
        "Faridpur",
    ),
    (
        "nasima.jute@poshra.test",
        "shitalpati",
        "Shitalpati mat, fine weave",
        "Murta cane split fine and woven close, so the surface stays cool through the afternoon.",
        "Murta cane",
        "2m x 1.5m",
        560000,
        2,
        9,
        "Sylhet",
    ),
]


class Command(BaseCommand):
    help = "Seed crafts, artisans and products for development and demos."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete seeded data first")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            Product.objects.all().delete()
            ArtisanProfile.objects.all().delete()
            Craft.objects.all().delete()
            self.stdout.write("cleared existing catalog")

        crafts = {}
        for row in CRAFTS:
            craft, _ = Craft.objects.update_or_create(slug=row["slug"], defaults=row)
            crafts[craft.slug] = craft

        profiles = {}
        for row in ARTISANS:
            user, created = User.objects.get_or_create(
                email=row["email"],
                defaults={"full_name": row["display_name"], "role": Role.ARTISAN},
            )
            if created:
                # Demo accounts: a known password, never used outside seeding.
                user.set_password("poshra-demo-artisan")
                user.save(update_fields=["password"])

            profile, _ = ArtisanProfile.objects.update_or_create(
                user=user,
                defaults={
                    "display_name": row["display_name"],
                    "story": row["story"],
                    "division": row["division"],
                    "district": row["district"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "verified_at": timezone.now() if row["verified"] else None,
                },
            )
            profile.crafts.set(crafts[slug] for slug in row["crafts"])
            profiles[row["email"]] = profile

        for (
            email,
            craft_slug,
            title,
            description,
            materials,
            dimensions,
            price_minor,
            stock,
            lead_time,
            origin,
        ) in PRODUCTS:
            Product.objects.update_or_create(
                artisan=profiles[email],
                title=title,
                defaults={
                    "craft": crafts[craft_slug],
                    "description": description,
                    "materials": materials,
                    "dimensions": dimensions,
                    "price_minor": price_minor,
                    "currency": "BDT",
                    "stock": stock,
                    "lead_time_days": lead_time,
                    "origin_district": origin,
                    "status": ProductStatus.PUBLISHED,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"seeded {Craft.objects.count()} crafts, "
                f"{ArtisanProfile.objects.count()} artisans, "
                f"{Product.objects.count()} products"
            )
        )
