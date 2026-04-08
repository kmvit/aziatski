from django.core.management.base import BaseCommand
from main.models import SiteSettings, House, Activity


class Command(BaseCommand):
    help = 'Seed initial data for the site'

    def handle(self, *args, **options):
        # Site Settings
        settings = SiteSettings.load()
        settings.hero_title = 'Отдых в горах Кавказа'
        settings.hero_subtitle = 'Уютные дома в живописном поселке Азиатский у реки Большая Лаба. Тишина, горы, чистый воздух и настоящий кавказский отдых.'
        settings.about_title = 'Поселок Азиатский'
        settings.about_text = (
            'Азиатский — небольшой горный поселок в Урупском районе Карачаево-Черкесии, '
            'расположенный у слияния горных рек с Большой Лабой. Основанный в 1934 году как '
            'приисковый поселок золотоискателей, сегодня он стал тихим и ухоженным местом, '
            'окружённым величественными горами Кавказа.\n\n'
            'Здесь нет суеты и шума города — только звук горной реки, пение птиц и свежий '
            'горный воздух. Поселок расположен на автодороге Псемён — Пхия, что делает его '
            'удобной отправной точкой для множества маршрутов по Кавказским горам.\n\n'
            'Мы предлагаем уютные дома для отдыха с видом на горы, оборудованные всем '
            'необходимым. Рядом — река с пляжем, баня, и множество активностей на любой вкус.'
        )
        settings.phone = '+7 (999) 123-45-67'
        settings.whatsapp = '79991234567'
        settings.telegram = 'aziatskiy_dom'
        settings.address = 'КЧР, Урупский район, п. Азиатский'
        settings.yandex_map_embed = '<iframe src="https://yandex.ru/map-widget/v1/?um=constructor%3Aaziatskiy&amp;source=constructor" width="100%" height="400" frameborder="0"></iframe>'
        settings.save()
        self.stdout.write(self.style.SUCCESS('Site settings created'))

        # Houses
        houses_data = [
            {
                'name': 'Дом у реки',
                'slug': 'dom-u-reki',
                'tagline': 'С панорамным видом на Большую Лабу',
                'description': (
                    'Просторный дом на первой линии реки Большая Лаба. '
                    'Из окон открывается завораживающий вид на горную реку и лесистые склоны.\n\n'
                    'Дом оборудован всем необходимым для комфортного отдыха: '
                    'полностью укомплектованная кухня, уютная гостиная с камином, '
                    'терраса с мангальной зоной и прямой выход к реке.'
                ),
                'price_per_night': 5000,
                'guests_count': 6,
                'bedrooms': 2,
                'beds': 3,
                'bathrooms': 1,
                'amenities': 'Wi-Fi\nКухня\nКамин\nТерраса\nМангал\nПарковка\nПостельное бельё\nПолотенца\nГорячая вода\nВид на реку',
                'order': 1,
            },
            {
                'name': 'Горный дом',
                'slug': 'gornyj-dom',
                'tagline': 'На возвышенности с видом на хребет',
                'description': (
                    'Уютный дом на возвышенности с потрясающим видом на горный хребет. '
                    'Идеально подходит для тех, кто хочет просыпаться среди облаков.\n\n'
                    'Большая открытая веранда, откуда можно наблюдать закаты за горами. '
                    'Внутри — тепло и комфорт: деревянная отделка, мягкая мебель, '
                    'современная техника.'
                ),
                'price_per_night': 4500,
                'guests_count': 4,
                'bedrooms': 2,
                'beds': 2,
                'bathrooms': 1,
                'amenities': 'Wi-Fi\nКухня\nВеранда\nМангал\nПарковка\nПостельное бельё\nПолотенца\nГорячая вода\nВид на горы\nОтопление',
                'order': 2,
            },
            {
                'name': 'Лесной домик',
                'slug': 'lesnoj-domik',
                'tagline': 'Уютный коттедж в окружении леса',
                'description': (
                    'Компактный и невероятно уютный домик в окружении вековых деревьев. '
                    'Полная тишина и единение с природой.\n\n'
                    'Идеален для пары или небольшой семьи. '
                    'Есть всё необходимое: кухня, душ, комфортная спальня. '
                    'На территории — беседка с мангалом и гамак между деревьями.'
                ),
                'price_per_night': 3500,
                'guests_count': 3,
                'bedrooms': 1,
                'beds': 2,
                'bathrooms': 1,
                'amenities': 'Wi-Fi\nКухня\nБеседка\nМангал\nГамак\nПарковка\nПостельное бельё\nПолотенца\nГорячая вода',
                'order': 3,
            },
            {
                'name': 'Большой дом',
                'slug': 'bolshoj-dom',
                'tagline': 'Для большой компании или семейного отдыха',
                'description': (
                    'Просторный двухэтажный дом для большой компании. '
                    'Три спальни, большая гостиная, полностью оборудованная кухня.\n\n'
                    'На территории — просторная терраса с мангальной зоной, '
                    'баня с комнатой отдыха, парковка на несколько машин. '
                    'Рядом — выход к реке и тропы для прогулок.'
                ),
                'price_per_night': 8000,
                'guests_count': 10,
                'bedrooms': 3,
                'beds': 5,
                'bathrooms': 2,
                'amenities': 'Wi-Fi\nКухня\nБаня\nТерраса\nМангал\nПарковка\nПостельное бельё\nПолотенца\nГорячая вода\nСтиральная машина\nВид на горы\nДетская площадка',
                'order': 4,
            },
        ]

        for data in houses_data:
            House.objects.update_or_create(slug=data['slug'], defaults=data)
        self.stdout.write(self.style.SUCCESS(f'{len(houses_data)} houses created'))

        # Activities
        activities_data = [
            {'name': 'Джипинг', 'description': 'Захватывающие маршруты по горным дорогам с потрясающими видами на Кавказский хребет', 'icon': 'car', 'order': 1},
            {'name': 'Квадроциклы', 'description': 'Поездки на квадроциклах по живописным горным тропам и лесным дорогам', 'icon': 'bike', 'order': 2},
            {'name': 'Сплав по реке', 'description': 'Рафтинг по горной реке Большая Лаба — от спокойных участков до порогов', 'icon': 'waves', 'order': 3},
            {'name': 'Хайкинг', 'description': 'Пешие маршруты по горам различной сложности с невероятными панорамами', 'icon': 'footprints', 'order': 4},
            {'name': 'Пляж у Лабы', 'description': 'Чистая горная река с пляжными участками — идеальное место в жаркий день', 'icon': 'umbrella', 'order': 5},
            {'name': 'Баня', 'description': 'Настоящая русская баня на дровах — лучший отдых после активного дня в горах', 'icon': 'flame', 'order': 6},
            {'name': 'Маршруты', 'description': 'Множество проверенных маршрутов к водопадам, озёрам и горным вершинам', 'icon': 'map', 'order': 7},
            {'name': 'Кемпинг', 'description': 'Ночёвки под звёздами в горах — для тех, кто хочет полного единения с природой', 'icon': 'tent', 'order': 8},
        ]

        for data in activities_data:
            Activity.objects.update_or_create(name=data['name'], defaults=data)
        self.stdout.write(self.style.SUCCESS(f'{len(activities_data)} activities created'))

        self.stdout.write(self.style.SUCCESS('All seed data created successfully!'))
