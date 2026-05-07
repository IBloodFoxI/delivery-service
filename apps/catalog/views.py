from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from .models import Product, Category, Favorite


def _favorites_set(user):
    if user.is_authenticated:
        return set(Favorite.objects.filter(user=user).values_list('product_id', flat=True))
    return set()


def home_view(request):
    categories = Category.objects.prefetch_related('products').all()
    category_slug = request.GET.get('category', '')
    search = request.GET.get('search', '')

    products = Product.objects.select_related('category').filter(is_available=True)

    if category_slug:
        products = products.filter(category__slug=category_slug)
    if search:
        products = products.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    active_category = None
    if category_slug:
        active_category = Category.objects.filter(slug=category_slug).first()

    return render(request, 'catalog/home.html', {
        'categories': categories,
        'products': products,
        'active_category': active_category,
        'search': search,
        'favorites': _favorites_set(request.user),
    })


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_available=True)
    similar = product.similar_products.filter(is_available=True)[:4]
    return render(request, 'catalog/product_detail.html', {
        'product': product,
        'similar': similar,
        'favorites': _favorites_set(request.user),
    })


@require_POST
@login_required
def toggle_favorite(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    fav, created = Favorite.objects.get_or_create(user=request.user, product=product)
    if not created:
        fav.delete()
        return JsonResponse({'is_favorite': False})
    return JsonResponse({'is_favorite': True})


@login_required
def favorites_list(request):
    favs = Favorite.objects.filter(user=request.user).select_related('product__category')
    products = [f.product for f in favs]
    return render(request, 'catalog/favorites.html', {
        'products': products,
        'favorites': _favorites_set(request.user),
    })
