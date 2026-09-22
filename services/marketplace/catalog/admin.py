from django.contrib import admin

from catalog.models import ArtisanProfile, Craft, Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Craft)
class CraftAdmin(admin.ModelAdmin):
    list_display = ("name", "name_bn", "home_district", "home_division")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "name_bn")


@admin.register(ArtisanProfile)
class ArtisanProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "district", "division", "is_verified")
    list_filter = ("division", "crafts")
    search_fields = ("display_name", "district", "user__email")
    prepopulated_fields = {"slug": ("display_name",)}
    filter_horizontal = ("crafts",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "artisan", "craft", "price_minor", "currency", "stock", "status")
    list_filter = ("status", "craft", "currency")
    search_fields = ("title", "description", "artisan__display_name")
    inlines = [ProductImageInline]
    autocomplete_fields = ("artisan", "craft")
