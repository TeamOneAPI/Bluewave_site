import jwt
from django.conf import settings
from datetime import datetime, timezone

def generate_api_jwt(user, expires_seconds=None):
    """
    Backwards-compatible quick generator (keeps previous behaviour).
    """
    import time
    exp = int((datetime.now(timezone.utc).timestamp() + (expires_seconds or getattr(settings, "JWT_API_EXP_SECONDS", 60*60*24))))
    payload = {
        "user_id": user.id,
        "email": user.email,
        "exp": exp,
    }
    token = jwt.encode(payload, settings.JWT_API_SECRET, algorithm=settings.JWT_API_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def generate_subscription_jwt(subscription):
    """
    Generate a JWT that expires exactly when the subscription end_date is reached.
    Expects subscription.end_date to be timezone-aware (Django's DateTimeField with USE_TZ=True).
    """
    # If end_date is naive, treat as UTC
    end = subscription.end_date
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    exp_ts = int(end.timestamp())
    payload = {
        "user_id": subscription.user.id,
        "email": subscription.user.email,
        "tier": subscription.tier,
        "sub_id": str(subscription.id),
        "exp": exp_ts,
    }
    token = jwt.encode(payload, settings.JWT_API_SECRET, algorithm=settings.JWT_API_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token