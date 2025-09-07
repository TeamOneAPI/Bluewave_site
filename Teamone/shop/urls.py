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

    # Cart
    path("cart/", views.view_cart, name="view_cart"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/remove/<int:item_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("cart/create-checkout-session/", views.create_cart_checkout_session, name="create_cart_checkout_session"),
    path("cart-success/", views.cart_success, name="cart_success"),
    path("cart-cancel/", views.cart_cancel, name="cart_cancel"),
    path("orders/", views.my_orders, name="my_orders"),
]
