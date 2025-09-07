from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from decimal import Decimal
import uuid


class User(AbstractUser):
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.email or self.username


class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="products/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    stock = models.IntegerField(default=10)

    def __str__(self):
        return self.name


class Cart(models.Model):
    user = models.ForeignKey("shop.User", related_name="carts", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    checked_out = models.BooleanField(default=False)

    def __str__(self):
        return f"Cart {self.id} for {self.user}"

    @property
    def total(self):
       return sum([item.subtotal for item in self.items.all()])



class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def subtotal(self) -> Decimal:
        return Decimal(self.quantity) * self.product.price

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


class EnvironmentalMetric(models.Model):
    product = models.ForeignKey(Product, related_name="metrics", on_delete=models.CASCADE)
    recorded_at = models.DateTimeField(default=timezone.now)
    salinity = models.FloatField(null=True, blank=True)
    ph = models.FloatField(null=True, blank=True)
    pollutant_index = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-recorded_at"]


class Subscription(models.Model):
    TIER_CHOICES = [
        ("basic", "Basic"),
        ("pro", "Pro"),
        ("research", "Research"),
    ]

    months = models.IntegerField(default=1)
    user = models.ForeignKey("shop.User", related_name="subscriptions", on_delete=models.CASCADE)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    active = models.BooleanField(default=False)

    # API token (JWT)
    api_key = models.CharField(max_length=512, blank=True, null=True)

    # Stripe integration
    order_id = models.UUIDField(default=uuid.uuid4, editable=False)
    stripe_checkout_session = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    TIER_PRICES = {
        "basic": Decimal("10.00"),
        "pro": Decimal("50.00"),
        "research": Decimal("200.00"),
    }

    def save(self, *args, **kwargs):
        # auto-assign price if not set
        if not self.price or self.price == Decimal("0.00"):
            monthly_price = self.TIER_PRICES.get(self.tier, Decimal("0.00"))
            self.price = (monthly_price * Decimal(self.months)).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} - {self.tier} (${self.price}) ({'active' if self.active else 'inactive'})"
    