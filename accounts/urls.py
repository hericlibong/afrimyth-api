"""Authentication routes.

The two token routes are explicitly public: a client cannot authenticate
before it holds a token. `me` requires a valid access token.
"""

from django.urls import path

from accounts.views import CurrentUserView, TokenObtainView, TokenRefreshAccessView

urlpatterns = [
    path("token/", TokenObtainView.as_view(), name="token-obtain-pair"),
    path("token/refresh/", TokenRefreshAccessView.as_view(), name="token-refresh"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
]
