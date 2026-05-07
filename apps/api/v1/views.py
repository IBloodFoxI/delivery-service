from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db import transaction
from .serializers import (
    UserSerializer, RegisterSerializer, CategorySerializer, ProductSerializer,
    CartSerializer, CartItemSerializer, OrderSerializer, OrderCreateSerializer,
    SupportTicketSerializer, TicketMessageSerializer,
    BalanceTopUpSerializer, BalanceTransactionSerializer
)
from apps.accounts.models import User, BalanceTransaction
from apps.catalog.models import Category, Product
from apps.orders.models import Cart, CartItem, Order, OrderItem, Delivery
from apps.support.models import SupportTicket, TicketMessage


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.is_admin_role or request.user.is_staff)


class IsSupportOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_support or request.user.is_admin_role or request.user.is_staff
        )


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        phone = request.data.get('phone_number')
        password = request.data.get('password')
        user = authenticate(username=phone, password=password)
        if not user:
            return Response({'error': 'Неверный телефон или пароль'}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({'error': 'Аккаунт заблокирован'}, status=status.HTTP_403_FORBIDDEN)
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class BalanceTopUpView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BalanceTopUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']
        with transaction.atomic():
            request.user.balance += amount
            request.user.save(update_fields=['balance'])
            tx = BalanceTransaction.objects.create(
                user=request.user,
                amount=amount,
                transaction_type=BalanceTransaction.TransactionType.TOPUP,
                description=f'Пополнение через API'
            )
        return Response({
            'balance': request.user.balance,
            'transaction': BalanceTransactionSerializer(tx).data
        })


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.filter(is_available=True).select_related('category')
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ['category', 'is_available']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'name']


class CartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(CartSerializer(cart).data)

    def post(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))
        try:
            product = Product.objects.get(id=product_id, is_available=True)
        except Product.DoesNotExist:
            return Response({'error': 'Товар не найден'}, status=404)
        item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        if not created:
            item.quantity += quantity
        else:
            item.quantity = quantity
        item.save()
        return Response(CartSerializer(cart).data)

    def delete(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart.items.all().delete()
        return Response(status=204)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_customer:
            return Order.objects.filter(user=user).prefetch_related('items').select_related('delivery')
        elif user.is_courier:
            return Order.objects.filter(courier=user).prefetch_related('items')
        elif user.is_support or user.is_admin_role or user.is_staff:
            return Order.objects.all().select_related('user', 'courier').prefetch_related('items')
        return Order.objects.none()

    def create(self, request, *args, **kwargs):
        if not request.user.is_customer:
            return Response({'error': 'Только покупатели могут создавать заказы'}, status=403)
        try:
            cart = request.user.cart
        except Cart.DoesNotExist:
            return Response({'error': 'Корзина пуста'}, status=400)

        items = cart.items.select_related('product').all()
        if not items.exists():
            return Response({'error': 'Корзина пуста'}, status=400)

        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        total = cart.total_price

        if request.user.balance < total:
            return Response({'error': f'Недостаточно средств. Баланс: {request.user.balance}'}, status=400)

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                total_price=total,
                status=Order.Status.PENDING,
                **serializer.validated_data
            )
            for item in items:
                OrderItem.objects.create(
                    order=order, product=item.product,
                    product_name=item.product.name,
                    quantity=item.quantity, price=item.product.price
                )
            request.user.balance -= total
            request.user.save(update_fields=['balance'])
            BalanceTransaction.objects.create(
                user=request.user, amount=-total,
                transaction_type=BalanceTransaction.TransactionType.PAYMENT,
                description=f'Оплата заказа #{order.id}'
            )
            # Назначить курьера
            courier = User.objects.filter(role=User.Role.COURIER, is_active=True).first()
            if courier:
                order.courier = courier
                order.status = Order.Status.ASSIGNED
                order.save(update_fields=['courier', 'status'])
                Delivery.objects.create(order=order, courier=courier, estimated_minutes=30)
            cart.items.all().delete()

        return Response(OrderSerializer(order).data, status=201)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        if not request.user.is_courier:
            return Response({'error': 'Только для курьеров'}, status=403)
        order = self.get_object()
        if order.status != Order.Status.PENDING:
            return Response({'error': 'Заказ уже назначен'}, status=400)
        order.courier = request.user
        order.status = Order.Status.ASSIGNED
        order.save()
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        if not request.user.is_courier:
            return Response({'error': 'Только для курьеров'}, status=403)
        order = self.get_object()
        from django.utils import timezone
        order.status = Order.Status.IN_PROGRESS
        order.save()
        if hasattr(order, 'delivery'):
            order.delivery.started_at = timezone.now()
            order.delivery.save()
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        if not request.user.is_courier:
            return Response({'error': 'Только для курьеров'}, status=403)
        order = self.get_object()
        from django.utils import timezone
        order.status = Order.Status.DELIVERED
        order.save()
        if hasattr(order, 'delivery'):
            order.delivery.completed_at = timezone.now()
            order.delivery.save()
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        if not (request.user.is_support or request.user.is_admin_role or request.user.is_staff):
            return Response({'error': 'Недостаточно прав'}, status=403)
        order = self.get_object()
        if order.status in [Order.Status.DELIVERED, Order.Status.CANCELLED]:
            return Response({'error': 'Невозможно отменить'}, status=400)
        with transaction.atomic():
            order.status = Order.Status.CANCELLED
            order.save()
            order.user.balance += order.total_price
            order.user.save(update_fields=['balance'])
            BalanceTransaction.objects.create(
                user=order.user, amount=order.total_price,
                transaction_type=BalanceTransaction.TransactionType.REFUND,
                description=f'Возврат за заказ #{order.id}'
            )
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=['patch'])
    def location(self, request, pk=None):
        if not request.user.is_courier:
            return Response({'error': 'Только для курьеров'}, status=403)
        order = self.get_object()
        coords = request.data.get('coords', '')
        if hasattr(order, 'delivery'):
            order.delivery.courier_location_stub = coords
            order.delivery.save(update_fields=['courier_location_stub'])
        return Response({'coords': coords})


class SupportTicketViewSet(viewsets.ModelViewSet):
    serializer_class = SupportTicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_customer:
            return SupportTicket.objects.filter(user=user).prefetch_related('messages')
        return SupportTicket.objects.all().prefetch_related('messages').select_related('user', 'order')

    def perform_create(self, serializer):
        order_id = self.request.data.get('order')
        try:
            order = Order.objects.get(id=order_id, user=self.request.user)
        except Order.DoesNotExist:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'order': 'Заказ не найден'})
        serializer.save(user=self.request.user, order=order)

    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        ticket = self.get_object()
        msg = TicketMessage.objects.create(
            ticket=ticket, author=request.user,
            message=request.data.get('message', '')
        )
        return Response(TicketMessageSerializer(msg).data, status=201)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        if not (request.user.is_support or request.user.is_admin_role or request.user.is_staff):
            return Response({'error': 'Недостаточно прав'}, status=403)
        ticket = self.get_object()
        ticket.status = SupportTicket.Status.CLOSED
        ticket.save()
        return Response({'status': 'closed'})
