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
