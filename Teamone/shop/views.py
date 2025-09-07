import stripe
import json
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, HttpResponse, redirect
from django.core.paginator import Paginator
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_POST

from .models import (
    Cart,
    CartItem,
    Product,
    EnvironmentalMetric,
    Subscription,
)
from .jwt_utils import generate_subscription_jwt

# Stripe config
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")

User = get_user_model()


# ------------------------------
# Product views
# ------------------------------

def product_list(request):
    qs = Product.objects.all().order_by("-created_at")
    paginator = Paginator(qs, getattr(settings, "PRODUCTS_PER_PAGE", 12))
    page_number = request.GET.get("page")
    page = paginator.get_page(page_number)
    return render(request, "shop/product_list.html", {"page": page})


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    metrics = product.metrics.all()[:10]
    return render(request, "shop/product_detail.html", {"product": product, "metrics": metrics})


# ------------------------------
# Subscriptions & Dashboard
# ------------------------------

def _monthly_price_for_tier(tier: str) -> Decimal:
    """Helper to get monthly price for tier from settings, returns Decimal."""
    tier_map = getattr(settings, "SUBSCRIPTION_TIERS", {"basic": 10.0, "pro": 50.0, "research": 200.0})
    try:
        monthly = Decimal(str(tier_map.get(tier, 0.0)))
    except (InvalidOperation, TypeError):
        monthly = Decimal("0.0")
    return monthly


@login_required
def dashboard(request):
    subs = request.user.subscriptions.all()
    latest_sub = subs.order_by("-end_date").first()
    api_token = latest_sub.api_key if latest_sub and latest_sub.active else None

    # cart summary
    cart = Cart.objects.filter(user=request.user, checked_out=False).first()
    orders = Cart.objects.filter(user=request.user, checked_out=True).prefetch_related("items__product")

    cart_items, cart_total = [], Decimal("0.00")
    if cart:
        cart_items = cart.items.select_related("product").all()
        cart_total = sum([i.subtotal for i in cart_items])

    return render(
        request,
        "shop/dashboard.html",
        {
            "subscriptions": subs,  # ✅ pass actual Subscription queryset
            "api_token": api_token,
            "STRIPE_PUBLISHABLE_KEY": settings.STRIPE_PUBLISHABLE_KEY,
            "tier_prices": getattr(
                settings, "SUBSCRIPTION_TIERS",
                {"basic": 10.0, "pro": 50.0, "research": 200.0}
            ),
            "cart_items": cart_items,
            "cart_total": cart_total,
            "orders": orders,
        },
    )


@login_required
def create_checkout_session(request):
    """Create a Stripe Checkout session for a subscription."""
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    tier = data.get("tier", "basic")
    months = int(data.get("months", 1))
    if months <= 0:
        months = 1
    if months > 24:
        months = 24

    PRICE_MAP = getattr(settings, "STRIPE_PRICE_MAP", {})
    price_id = PRICE_MAP.get(tier)
    if not price_id:
        return JsonResponse({"error": "Invalid tier or Stripe price not configured"}, status=400)

    end_date = timezone.now() + timedelta(days=30 * months)

    monthly_price = _monthly_price_for_tier(tier)
    total_price = (monthly_price * Decimal(months)).quantize(Decimal("0.01"))

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=request.build_absolute_uri("/stripe-success/") + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri("/stripe-cancel/"),
            metadata={"user_id": str(request.user.id), "tier": tier, "months": str(months)},
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
