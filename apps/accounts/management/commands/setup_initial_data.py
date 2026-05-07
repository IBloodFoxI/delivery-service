from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Создаёт начальные данные: категории, товары, демо-пользователей'

    def handle(self, *args, **options):
        self._create_users()
        self._create_catalog()
        self.stdout.write(self.style.SUCCESS('Начальные данные созданы успешно'))

    @transaction.atomic
    def _create_users(self):
        from apps.accounts.models import User

        users = [
            dict(phone_number='+79000000001', full_name='Администратор Системы',
                 role='admin', is_staff=True, is_superuser=True, balance='0.00', password='admin123'),
            dict(phone_number='+79000000002', full_name='Иванов Алексей Петрович',
                 role='courier', email='deniska3108@gmail.com', balance='0.00', password='courier123'),
            dict(phone_number='+79000000003', full_name='Петрова Мария Сергеевна',
                 role='support', balance='0.00', password='support123'),
            dict(phone_number='+79000000004', full_name='Сидоров Дмитрий Олегович',
                 role='customer', balance='1500.00', password='customer123'),
            dict(phone_number='+79000000005', full_name='Козлова Анна Викторовна',
                 role='courier', balance='0.00', password='courier456'),
        ]

        for data in users:
            from apps.accounts.crypto import make_hash, encrypt
            password = data.pop('password')
            phone = data.pop('phone_number')
            email = data.pop('email', '')
            phone_h = make_hash(phone)

            if not User.objects.filter(phone_hash=phone_h).exists():
                user = User(**data)
                user.set_phone(phone)
                if email:
                    user.set_email_encrypted(email)
                user.set_password(password)
                user.save()
                self.stdout.write(f'  Создан пользователь {phone}')
            else:
                # Обновляем email если он задан и ещё не установлен
                if email:
                    User.objects.filter(phone_hash=phone_h, email_hash='').update(
                        email=encrypt(email),
                        email_hash=make_hash(email),
                    )
                self.stdout.write(f'  Пользователь {phone} уже существует, пропускаем')

    @transaction.atomic
    def _create_catalog(self):
        from apps.catalog.models import Category, Product

        categories_data = [
            {'name': 'Молоко и яйца', 'slug': 'molochnye-produkty', 'order': 1},
            {'name': 'Мясо и птица', 'slug': 'myaso-i-ptitsa', 'order': 2},
            {'name': 'Фрукты', 'slug': 'frukty', 'order': 3},
            {'name': 'Овощи', 'slug': 'ovoshchi', 'order': 4},
            {'name': 'Хлеб и выпечка', 'slug': 'khlib-i-vypechka', 'order': 5},
            {'name': 'Напитки', 'slug': 'napitki', 'order': 6},
        ]

        cats = {}
        for cat_data in categories_data:
            cat, created = Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults={'name': cat_data['name'], 'order': cat_data['order']}
            )
            cats[cat_data['slug']] = cat
            if created:
                self.stdout.write(f'  Категория: {cat.name}')

        products_data = [
            # Молоко и яйца
            {'category': 'molochnye-produkty', 'name': 'Молоко 3.2% Простоквашино', 'price': '89.90',
             'weight': 930, 'calories': '58.0', 'proteins': '2.9', 'fats': '3.2', 'carbs': '4.7',
             'description': 'Пастеризованное коровье молоко. Без добавок.',
             'image': 'products/Moloko.jpg'},
            {'category': 'molochnye-produkty', 'name': 'Яйца куриные C1 10 шт', 'price': '109.90',
             'weight': 600, 'calories': '157.0', 'proteins': '12.7', 'fats': '11.5', 'carbs': '0.7',
             'description': 'Яйца куриные категории C1. Первая свежесть.',
             'image': 'products/Eggs.png'},
            {'category': 'molochnye-produkty', 'name': 'Кефир 2.5% Простоквашино', 'price': '79.90',
             'weight': 900, 'calories': '51.0', 'proteins': '2.8', 'fats': '2.5', 'carbs': '4.0',
             'description': 'Кисломолочный напиток. Улучшает пищеварение.',
             'image': 'products/Kefir.jpg'},
            {'category': 'molochnye-produkty', 'name': 'Масло сливочное 82.5% Вологодское', 'price': '219.90',
             'weight': 200, 'calories': '748.0', 'proteins': '0.5', 'fats': '82.5', 'carbs': '0.8',
             'description': 'Сладкосливочное несолёное масло. ГОСТ Р 52253.',
             'image': 'products/Maslo.jpg'},
            # Мясо и птица
            {'category': 'myaso-i-ptitsa', 'name': 'Куриная грудка охлаждённая', 'price': '349.90',
             'weight': 700, 'calories': '113.0', 'proteins': '23.6', 'fats': '1.9', 'carbs': '0.4',
             'description': 'Куриная грудка без кожи. Отличный источник белка.',
             'image': 'products/Grudka.jpg'},
            {'category': 'myaso-i-ptitsa', 'name': 'Фарш говяжий охлаждённый', 'price': '429.90',
             'weight': 500, 'calories': '218.0', 'proteins': '17.2', 'fats': '16.1', 'carbs': '0.0',
             'description': 'Рубленый говяжий фарш из свежего мяса.',
             'image': 'products/Farsh.jpg'},
            {'category': 'myaso-i-ptitsa', 'name': 'Окорочка куриные охлаждённые', 'price': '259.90',
             'weight': 900, 'calories': '158.0', 'proteins': '16.8', 'fats': '10.2', 'carbs': '0.0',
             'description': 'Куриные окорочка охлаждённые. Идеальны для запекания.',
             'image': 'products/Okorochok.jpg'},
            # Фрукты
            {'category': 'frukty', 'name': 'Бананы', 'price': '89.90',
             'weight': 1000, 'calories': '89.0', 'proteins': '1.1', 'fats': '0.3', 'carbs': '22.8',
             'description': 'Спелые бананы. Богаты калием и магнием.',
             'image': 'products/Banana.jpg'},
            {'category': 'frukty', 'name': 'Яблоки Фуджи', 'price': '149.90',
             'weight': 1000, 'calories': '52.0', 'proteins': '0.3', 'fats': '0.2', 'carbs': '13.8',
             'description': 'Сочные яблоки сорта Фуджи. Сладкие с лёгкой кислинкой.',
             'image': 'products/Fudji_apple.png'},
            {'category': 'frukty', 'name': 'Апельсины', 'price': '129.90',
             'weight': 1000, 'calories': '43.0', 'proteins': '0.9', 'fats': '0.2', 'carbs': '8.1',
             'description': 'Сладкие апельсины. Богаты витамином C.',
             'image': 'products/Orange.jpg'},
            # Овощи
            {'category': 'ovoshchi', 'name': 'Помидоры черри', 'price': '199.90',
             'weight': 500, 'calories': '27.0', 'proteins': '1.3', 'fats': '0.3', 'carbs': '3.5',
             'description': 'Томаты черри. Сочные и сладкие.',
             'image': 'products/tomato_cherry.jpg'},
            {'category': 'ovoshchi', 'name': 'Огурцы тепличные', 'price': '99.90',
             'weight': 500, 'calories': '14.0', 'proteins': '0.8', 'fats': '0.1', 'carbs': '2.5',
             'description': 'Свежие тепличные огурцы. Хрустящие.',
             'image': 'products/Cucumber.jpg'},
            {'category': 'ovoshchi', 'name': 'Картофель мытый', 'price': '69.90',
             'weight': 2000, 'calories': '77.0', 'proteins': '2.0', 'fats': '0.4', 'carbs': '16.3',
             'description': 'Картофель столовый мытый. Урожай текущего сезона.',
             'image': 'products/Potato.jpg'},
            # Хлеб и выпечка
            {'category': 'khlib-i-vypechka', 'name': 'Хлеб Бородинский', 'price': '69.90',
             'weight': 360, 'calories': '208.0', 'proteins': '6.7', 'fats': '1.3', 'carbs': '40.8',
             'description': 'Ржано-пшеничный хлеб с кориандром. Классический вкус.',
             'image': 'products/DarkBread.jpg'},
            {'category': 'khlib-i-vypechka', 'name': 'Батон нарезной', 'price': '49.90',
             'weight': 400, 'calories': '262.0', 'proteins': '8.1', 'fats': '2.8', 'carbs': '52.0',
             'description': 'Пшеничный батон высшего сорта.',
             'image': 'products/Bread_cutted.jpg'},
            # Напитки
            {'category': 'napitki', 'name': 'Вода питьевая Aqua Minerale 1.5л', 'price': '59.90',
             'weight': 1500, 'calories': '0.0', 'proteins': '0.0', 'fats': '0.0', 'carbs': '0.0',
             'description': 'Негазированная питьевая вода.',
             'image': 'products/AquaMinerale.jpg'},
            {'category': 'napitki', 'name': 'Сок апельсиновый Rich 1л', 'price': '149.90',
             'weight': 1000, 'calories': '46.0', 'proteins': '0.5', 'fats': '0.1', 'carbs': '10.4',
             'description': 'Восстановленный апельсиновый сок.',
             'image': 'products/RichOrange.jpg'},
            {'category': 'napitki', 'name': 'Кофе Nescafé Gold 190г', 'price': '349.90',
             'weight': 190, 'calories': '370.0', 'proteins': '14.0', 'fats': '3.0', 'carbs': '61.0',
             'description': 'Растворимый кофе. Насыщенный вкус и аромат.',
             'image': 'products/Nescafe.jpg'},
        ]

        products = {}
        for p_data in products_data:
            cat_slug = p_data.pop('category')
            image_path = p_data.pop('image')
            p_data['category'] = cats[cat_slug]
            product, created = Product.objects.get_or_create(
                name=p_data['name'],
                defaults=p_data
            )
            if not product.image:
                product.image = image_path
                product.save(update_fields=['image'])
            products[product.name] = product
            if created:
                self.stdout.write(f'  Товар: {product.name}')
            else:
                self.stdout.write(f'  Обновлено фото: {product.name}')

        # Similar products links
        similar_links = [
            ('Молоко 3.2% Простоквашино', 'Кефир 2.5% Danone'),
            ('Куриная грудка охлаждённая', 'Окорочка куриные охлаждённые'),
            ('Куриная грудка охлаждённая', 'Фарш говяжий охлаждённый'),
            ('Бананы', 'Яблоки Фуджи'),
            ('Бананы', 'Апельсины'),
            ('Яблоки Фуджи', 'Апельсины'),
            ('Помидоры черри', 'Огурцы тепличные'),
            ('Хлеб Бородинский', 'Батон нарезной'),
        ]
        for name_a, name_b in similar_links:
            if name_a in products and name_b in products:
                products[name_a].similar_products.add(products[name_b])
