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

    # create a pending subscription
    Subscription.objects.create(
        user=request.user,
        tier=tier,
        months=months,
        end_date=end_date,
        active=False,
        stripe_checkout_session=checkout_session.id,
        price=total_price,
    )

    return JsonResponse({"sessionId": checkout_session.id})


@csrf_exempt
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            event = json.loads(payload)
    except Exception:
        return HttpResponse(status=400)

    event_type = event.get("type")

    # checkout completed
    if event_type == "checkout.session.completed":
        sess = event["data"]["object"]
        checkout_id = sess.get("id")
        metadata = sess.get("metadata", {}) or {}
        user_id = metadata.get("user_id")

        # ✅ if it's a subscription
        if metadata.get("tier"):
            months = int(metadata.get("months", 1))
            tier = metadata.get("tier", "basic")
            sub = Subscription.objects.filter(stripe_checkout_session=checkout_id).first()
            if not sub and user_id:
                sub = Subscription.objects.filter(user__id=user_id, tier=tier, active=False).order_by("-start_date").first()
            if sub:
                sub.active = True
                sub.months = months
                sub.end_date = timezone.now() + timedelta(days=30 * months)
                monthly_price = _monthly_price_for_tier(sub.tier)
                sub.price = (monthly_price * Decimal(sub.months)).quantize(Decimal("0.01"))
                sub.api_key = generate_subscription_jwt(sub)
                sub.save()

        # ✅ if it's a cart checkout
        elif metadata.get("cart_id"):
            cart_id = metadata["cart_id"]
            cart = Cart.objects.filter(id=cart_id, user__id=user_id).first()
            if cart:
                cart.checked_out = True
                cart.save()

    return HttpResponse(status=200)



def stripe_success(request):
    return render(request, "shop/stripe_success.html")


def stripe_cancel(request):
    return render(request, "shop/stripe_cancel.html")


# ------------------------------
# Cart
# ------------------------------

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, _ = Cart.objects.get_or_create(user=request.user, checked_out=False)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.quantity += 1
        item.save()
    return redirect("view_cart")


@login_required
def view_cart(request):
    cart = Cart.objects.filter(user=request.user, checked_out=False).first()
    items = cart.items.select_related("product").all() if cart else []
    total = cart.total if cart else 0
    return render(request, "shop/cart.html", {"cart": cart, "items": items, "total": total})



@login_required
def remove_from_cart(request, item_id):
    CartItem.objects.filter(id=item_id, cart__user=request.user).delete()
    return redirect("view_cart")


# ------------------------------
# Dev helper
# ------------------------------

@login_required
@require_POST
def simulate_subscription(request):
    months = int(request.POST.get("months", 1)) if request.POST.get("months") else 1
    tier = request.POST.get("tier", "basic")
    if months <= 0:
        months = 1
    if months > 240:
        months = 240

    end_date = timezone.now() + timedelta(days=30 * months)
    monthly_price = _monthly_price_for_tier(tier)
    total_price = (monthly_price * Decimal(months)).quantize(Decimal("0.01"))

    sub = Subscription.objects.create(
        user=request.user,
        tier=tier,
        months=months,
        end_date=end_date,
        active=True,
        price=total_price,
    )

    sub.api_key = generate_subscription_jwt(sub)
    sub.save()

    return redirect("dashboard")

