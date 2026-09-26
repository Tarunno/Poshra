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
    # Credentials a shopper hands to an AI agent. Not under /auth/ for the
    # same reason users/me is not: minting one requires being signed in.
    path("agent-tokens", views.AgentTokensView.as_view(), name="agent-tokens"),
    path(
        "agent-tokens/introspect",
        views.AgentTokenIntrospectView.as_view(),
        name="agent-tokens-introspect",
    ),
    path("agent-tokens/<str:token_id>", views.AgentTokenView.as_view(), name="agent-token"),
]
