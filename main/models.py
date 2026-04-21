from django.db import models
from django.core.exceptions import ValidationError


class SiteSettings(models.Model):
    phone = models.CharField('Телефон', max_length=20, default='+7 (999) 123-45-67')
    whatsapp = models.CharField('WhatsApp', max_length=20, blank=True)
    telegram = models.CharField('Telegram', max_length=100, blank=True)
    address = models.CharField('Адрес', max_length=255, default='КЧР, Урупский район, п. Азиатский')
    hero_title = models.CharField('Заголовок Hero', max_length=200, default='Отдых в горах Кавказа')
    hero_subtitle = models.TextField('Подзаголовок Hero', default='Уютные дома в живописном поселке Азиатский у реки Большая Лаба')
    about_title = models.CharField('Заголовок "О поселке"', max_length=200, default='Поселок Азиатский')
    about_text = models.TextField('Текст "О поселке"', default='')
    about_image_1 = models.ImageField('Фото "О поселке" 1', upload_to='about/', blank=True, null=True)
    about_image_2 = models.ImageField('Фото "О поселке" 2', upload_to='about/', blank=True, null=True)
    about_image_3 = models.ImageField('Фото "О поселке" 3', upload_to='about/', blank=True, null=True)
    about_image_4 = models.ImageField('Фото "О поселке" 4', upload_to='about/', blank=True, null=True)
    yandex_map_embed = models.TextField('Код карты Яндекс (iframe)', blank=True)

    class Meta:
        verbose_name = 'Настройки сайта'
        verbose_name_plural = 'Настройки сайта'

    def __str__(self):
        return 'Настройки сайта'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class House(models.Model):
    name = models.CharField('Название', max_length=100)
    slug = models.SlugField('URL', unique=True)
    tagline = models.CharField('Краткое описание', max_length=200, blank=True)
    description = models.TextField('Описание')
    price_per_night = models.PositiveIntegerField('Цена за сутки будни (руб)')
    weekend_price = models.PositiveIntegerField('Цена за сутки выходные (руб)', null=True, blank=True, help_text='Если пусто — используется будничная цена')
    guests_count = models.PositiveSmallIntegerField('Кол-во гостей', default=4)
    bedrooms = models.PositiveSmallIntegerField('Спальни', default=1)
    beds = models.PositiveSmallIntegerField('Кровати', default=2)
    bathrooms = models.PositiveSmallIntegerField('Санузлы', default=1)
    amenities = models.TextField('Удобства', help_text='Каждое удобство с новой строки', blank=True)
    is_featured = models.BooleanField('Показывать на главной', default=True)
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Дом'
        verbose_name_plural = 'Дома'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def get_main_image(self):
        img = self.images.filter(is_main=True).first()
        return img or self.images.first()

    def amenities_list(self):
        return [a.strip() for a in self.amenities.split('\n') if a.strip()]


class HouseImage(models.Model):
    house = models.ForeignKey(House, on_delete=models.CASCADE, related_name='images', verbose_name='Дом')
    image = models.ImageField('Фото', upload_to='houses/')
    is_main = models.BooleanField('Главное фото', default=False)
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Фото дома'
        verbose_name_plural = 'Фото домов'
        ordering = ['order']

    def __str__(self):
        return f'{self.house.name} — фото {self.order}'


class Activity(models.Model):
    name = models.CharField('Название', max_length=100)
    description = models.TextField('Описание')
    icon = models.CharField('Иконка (Lucide)', max_length=50, help_text='Например: mountain, waves, flame', default='mountain')
    image = models.ImageField('Фото', upload_to='activities/', blank=True, null=True)
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Активность'
        verbose_name_plural = 'Активности'
        ordering = ['order']

    def __str__(self):
        return self.name


class SectionDivider(models.Model):
    POSITION_CHOICES = [
        ('after_houses', 'После блока Дома'),
        ('after_about', 'После блока О поселке'),
        ('after_gallery', 'После блока Галерея'),
    ]
    position = models.CharField('Позиция', max_length=20, choices=POSITION_CHOICES, unique=True)
    title = models.CharField('Заголовок', max_length=200)
    subtitle = models.CharField('Подзаголовок', max_length=300, blank=True)
    icon = models.CharField('Иконка (Lucide)', max_length=50, default='mountain')
    image = models.ImageField('Фоновое фото', upload_to='dividers/', blank=True, null=True)

    class Meta:
        verbose_name = 'Фото-разделитель'
        verbose_name_plural = 'Фото-разделители'

    def __str__(self):
        return f'{self.get_position_display()} — {self.title}'


class RouteCity(models.Model):
    name = models.CharField('Город', max_length=100)
    distance_km = models.PositiveIntegerField('Расстояние (км)')
    drive_time = models.CharField('Время в пути', max_length=50, help_text='Например: 5 ч 30 мин')
    description = models.TextField('Описание маршрута', blank=True, help_text='Через какие города, качество дороги и тд')
    lat = models.FloatField('Широта города', help_text='Для построения маршрута в Яндекс.Картах')
    lon = models.FloatField('Долгота города', help_text='Для построения маршрута в Яндекс.Картах')
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Маршрут из города'
        verbose_name_plural = 'Как добраться'
        ordering = ['order']

    def __str__(self):
        return f'{self.name} — {self.distance_km} км'


class HolidaySurcharge(models.Model):
    name = models.CharField('Название', max_length=100, help_text='Например: Новый год 2026, Майские')
    house = models.ForeignKey(House, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Дом', help_text='Пусто = для всех домов')
    date_from = models.DateField('Дата начала')
    date_to = models.DateField('Дата окончания')
    price_override = models.PositiveIntegerField('Фиксированная цена (руб)', null=True, blank=True, help_text='Абсолютная цена за сутки')
    percentage_markup = models.PositiveSmallIntegerField('Наценка (%)', null=True, blank=True, help_text='Например: 30 для +30% к базовой цене')
    is_active = models.BooleanField('Активна', default=True)
    order = models.PositiveSmallIntegerField('Приоритет', default=0, help_text='Чем выше — тем приоритетнее при пересечении')

    class Meta:
        verbose_name = 'Ценовая наценка'
        verbose_name_plural = 'Ценовые наценки'
        ordering = ['-order']

    def __str__(self):
        price = f'{self.price_override} ₽' if self.price_override else f'+{self.percentage_markup}%'
        return f'{self.name} ({self.date_from} — {self.date_to}) {price}'

    def clean(self):
        if self.date_to and self.date_from and self.date_to < self.date_from:
            raise ValidationError('Дата окончания должна быть >= даты начала')
        if not self.price_override and not self.percentage_markup:
            raise ValidationError('Укажите фиксированную цену или наценку в %')
        if self.price_override and self.percentage_markup:
            raise ValidationError('Укажите только одно: фиксированную цену ИЛИ наценку в %')


class GalleryImage(models.Model):
    image = models.ImageField('Фото', upload_to='gallery/')
    caption = models.CharField('Подпись', max_length=200, blank=True)
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Фото галереи'
        verbose_name_plural = 'Фотогалерея'
        ordering = ['order']

    def __str__(self):
        return self.caption or f'Фото {self.order}'


class BookingRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('confirmed', 'Подтверждена'),
        ('rejected', 'Отклонена'),
        ('cancelled', 'Отменена'),
    ]
    house = models.ForeignKey(House, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Дом', related_name='bookings')
    name = models.CharField('Имя', max_length=100)
    phone = models.CharField('Телефон', max_length=20)
    check_in = models.DateField('Дата заезда')
    check_out = models.DateField('Дата выезда')
    guests = models.PositiveSmallIntegerField('Кол-во гостей', default=1)
    message = models.TextField('Сообщение', blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending')
    total_price = models.PositiveIntegerField('Итого (руб)', null=True, blank=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Заявка на бронирование'
        verbose_name_plural = 'Заявки на бронирование'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} — {self.check_in} → {self.check_out}'

    def blocks_dates(self):
        return self.status == 'confirmed'
