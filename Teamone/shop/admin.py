from django.contrib import admin
from .models import User, Product, Cart, CartItem, EnvironmentalMetric, Subscription


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "phone_number", "is_staff", "is_active")
    search_fields = ("username", "email")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "stock", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at", "checked_out")
    list_filter = ("checked_out",)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "product", "quantity", "subtotal")


@admin.register(EnvironmentalMetric)
class EnvironmentalMetricAdmin(admin.ModelAdmin):
    list_display = ("product", "recorded_at", "salinity", "ph", "pollutant_index")
    list_filter = ("recorded_at",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "tier", "months", "start_date", "end_date", "active")
    list_filter = ("tier", "active")
