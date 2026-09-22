from django.urls import path

from accounts import views

urlpatterns = [
    path("auth/register", views.register, name="auth-register"),
    path("auth/login", views.login, name="auth-login"),
    path("auth/refresh", views.refresh, name="auth-refresh"),
    path("auth/logout", views.logout, name="auth-logout"),
    path("auth/jwks.json", views.jwks, name="auth-jwks"),
]
