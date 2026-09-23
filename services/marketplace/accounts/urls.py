from django.urls import path

from accounts import views

urlpatterns = [
    path("auth/register", views.RegisterView.as_view(), name="auth-register"),
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
    path("auth/refresh", views.RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", views.LogoutView.as_view(), name="auth-logout"),
    # Deliberately not under /auth/: that path is exempt from gateway
    # identity checks so that login and refresh can work without a token.
    path("users/me", views.MeView.as_view(), name="users-me"),
    path("auth/jwks.json", views.JWKSView.as_view(), name="auth-jwks"),
]
