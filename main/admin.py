from django import forms
from django.contrib import admin
from django.db.models import Max
from django.utils.html import format_html
from .models import SiteSettings, House, HouseImage, Activity, SectionDivider, RouteCity, HolidaySurcharge, GalleryImage, BookingRequest


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Контакты', {'fields': ('phone', 'whatsapp', 'telegram', 'address')}),
        ('Главный экран', {'fields': ('hero_title', 'hero_subtitle')}),
        ('О поселке', {'fields': ('about_title', 'about_text')}),
        ('Карта', {'fields': ('yandex_map_embed',)}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class HouseImageInline(admin.TabularInline):
    model = HouseImage
    extra = 1


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', MultipleImageInput(attrs={'multiple': True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        clean_single_file = super().clean
        return [clean_single_file(file, initial) for file in data]


class HouseAdminForm(forms.ModelForm):
    bulk_images = MultipleImageField(label='Загрузить несколько фото', help_text='Можно выбрать сразу несколько файлов.')

    class Meta:
        model = House
        fields = '__all__'


@admin.register(House)
class HouseAdmin(admin.ModelAdmin):
    form = HouseAdminForm
    list_display = ('name', 'price_per_night', 'weekend_price', 'guests_count', 'is_featured', 'order')
    list_editable = ('order', 'is_featured')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [HouseImageInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        files = form.cleaned_data.get('bulk_images') or []
        if not files:
            return

        max_order = form.instance.images.aggregate(max_order=Max('order')).get('max_order') or 0
        for index, image_file in enumerate(files, start=1):
            HouseImage.objects.create(
                house=form.instance,
                image=image_file,
                order=max_order + index,
            )


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'image', 'order')
    list_editable = ('order',)


@admin.register(SectionDivider)
class SectionDividerAdmin(admin.ModelAdmin):
    list_display = ('position', 'title')


@admin.register(RouteCity)
class RouteCityAdmin(admin.ModelAdmin):
    list_display = ('name', 'distance_km', 'drive_time', 'order')
    list_editable = ('order',)


@admin.register(HolidaySurcharge)
class HolidaySurchargeAdmin(admin.ModelAdmin):
    list_display = ('name', 'house_display', 'date_from', 'date_to', 'price_display', 'is_active')
    list_filter = ('is_active', 'house')
    list_editable = ('is_active',)

    def house_display(self, obj):
        return obj.house or 'Все дома'
    house_display.short_description = 'Дом'

    def price_display(self, obj):
        if obj.price_override:
            return f'{obj.price_override} ₽'
        return f'+{obj.percentage_markup}%'
    price_display.short_description = 'Цена'


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ('caption', 'order')
    list_editable = ('order',)


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'house', 'check_in', 'check_out', 'guests', 'total_price', 'status', 'status_colored', 'created_at')
    list_filter = ('status', 'house', 'created_at')
    list_editable = ('status',)
    list_display_links = ('name',)
    readonly_fields = ('created_at', 'total_price')
    actions = ['confirm_bookings', 'reject_bookings']

    # Note: list_editable requires 'status' field, but we also want colored display.
    # Django doesn't allow both list_editable and custom display for same field.
    # So we use 'status' in list_editable (dropdown) and a separate colored column.

    def status_colored(self, obj):
        colors = {
            'pending': '#f59e0b',
            'confirmed': '#22c55e',
            'rejected': '#ef4444',
            'cancelled': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html('<span style="color:{}; font-weight:600;">{}</span>', color, obj.get_status_display())
    status_colored.short_description = 'Статус'

    @admin.action(description='Подтвердить выбранные')
    def confirm_bookings(self, request, queryset):
        queryset.update(status='confirmed')

    @admin.action(description='Отклонить выбранные')
    def reject_bookings(self, request, queryset):
        queryset.update(status='rejected')
