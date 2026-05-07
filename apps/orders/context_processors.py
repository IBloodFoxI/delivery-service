def cart_count(request):
    if request.user.is_authenticated and request.user.is_customer:
        try:
            cart = request.user.cart
            return {'cart_count': cart.total_items}
        except Exception:
            pass
    return {'cart_count': 0}
