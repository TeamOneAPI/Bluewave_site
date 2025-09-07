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
