from django.db import models
from django.conf import settings
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название')
    slug = models.SlugField(unique=True, verbose_name='Слаг')
    image = models.ImageField(upload_to='categories/', null=True, blank=True, verbose_name='Изображение')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products', verbose_name='Категория')
    name = models.CharField(max_length=200, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Цена')
    image = models.ImageField(upload_to='products/', null=True, blank=True, verbose_name='Фото')
    weight = models.PositiveIntegerField(default=0, verbose_name='Вес (г)')

    # КБЖУ
    calories = models.DecimalField(max_digits=6, decimal_places=1, default=0, verbose_name='Калории (ккал/100г)')
    proteins = models.DecimalField(max_digits=5, decimal_places=1, default=0, verbose_name='Белки (г/100г)')
    fats = models.DecimalField(max_digits=5, decimal_places=1, default=0, verbose_name='Жиры (г/100г)')
    carbs = models.DecimalField(max_digits=5, decimal_places=1, default=0, verbose_name='Углеводы (г/100г)')

    similar_products = models.ManyToManyField('self', blank=True, verbose_name='Похожие товары')
    is_available = models.BooleanField(default=True, verbose_name='В наличии')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['category', 'name']

    def __str__(self):
        return self.name

    @property
    def kbju_per_product(self):
        if self.weight == 0:
            return None
        factor = self.weight / 100
        return {
            'calories': round(float(self.calories) * factor, 1),
            'proteins': round(float(self.proteins) * factor, 1),
            'fats': round(float(self.fats) * factor, 1),
            'carbs': round(float(self.carbs) * factor, 1),
        }


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites'
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'product']
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'

    def __str__(self):
        return f'{self.user} → {self.product}'
