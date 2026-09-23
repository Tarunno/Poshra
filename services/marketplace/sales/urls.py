from django.urls import path

from sales.views import SalesSummary

urlpatterns = [
    path("sales/summary", SalesSummary.as_view(), name="sales-summary"),
]
