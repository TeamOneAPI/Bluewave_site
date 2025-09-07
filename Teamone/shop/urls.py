from django.urls import path
from . import views

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),
    
    # Dashboard & subscriptions
    path("dashboard/", views.dashboard, name="dashboard"),
    path("create-checkout-session/", views.create_checkout_session, name="create_checkout_session"),
    path("simulate-subscription/", views.simulate_subscription, name="simulate_subscription"),
    path("cancel-subscription/<int:sub_id>/", views.cancel_subscription, name="cancel_subscription"),

    # Stripe webhooks & subscription flow
    path("stripe-webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("stripe-success/", views.stripe_success, name="stripe_success"),
    path("stripe-cancel/", views.stripe_cancel, name="stripe_cancel"),
