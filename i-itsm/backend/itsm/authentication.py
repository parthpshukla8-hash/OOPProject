from datetime import timedelta

from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

TOKEN_LIFETIME = timedelta(hours=24)


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if token.created + TOKEN_LIFETIME <= timezone.now():
            token.delete()
            raise AuthenticationFailed("Authentication token has expired.")
        return user, token
