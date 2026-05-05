from datetime import date, timedelta
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.db.models import Sum, Count, Q
from django.conf import settings
from django.core.mail import send_mail
from .models import SiteSettings, House, Activity, SectionDivider, RouteCity, GalleryImage, BookingRequest, BlogPost
from .forms import BookingForm
from .pricing import calculate_booking_price, get_booked_dates, get_prices_map, check_overlap

logger = logging.getLogger(__name__)


def index(request):
    settings = SiteSettings.load()
    houses = House.objects.filter(is_featured=True)
    activities = Activity.objects.all()
    gallery = GalleryImage.objects.all()
    dividers = {d.position: d for d in SectionDivider.objects.all()}
    routes = RouteCity.objects.all()
    return render(request, 'index.html', {
        'settings': settings,
        'houses': houses,
        'activities': activities,
        'gallery': gallery,
        'dividers': dividers,
        'routes': routes,
    })


def house_detail(request, slug):
    house = get_object_or_404(House, slug=slug)
    settings = SiteSettings.load()
    return render(request, 'house_detail.html', {
        'house': house,
        'settings': settings,
    })


def booking_page(request):
    houses = House.objects.filter(is_featured=True)
    settings = SiteSettings.load()
    return render(request, 'booking.html', {
        'houses': houses,
        'settings': settings,
    })


def booking_create(request):
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            # Calculate total price
            if booking.house and booking.check_in and booking.check_out:
                result = calculate_booking_price(booking.house, booking.check_in, booking.check_out)
                booking.total_price = result['total_price']
            booking.save()
            _send_booking_notification(booking)
            return JsonResponse({
                'success': True,
                'message': 'Заявка отправлена! Мы свяжемся с вами в ближайшее время.',
                'total_price': booking.total_price,
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def api_calendar_data(request, house_id):
    house = get_object_or_404(House, pk=house_id)
    months = int(request.GET.get('months', 4))
    booked = get_booked_dates(house, months)
    prices, holidays = get_prices_map(house, months)
    return JsonResponse({
        'booked_dates': booked,
        'prices': prices,
        'holidays': holidays,
    })


def api_calculate_price(request):
    house_id = request.GET.get('house_id')
    check_in_str = request.GET.get('check_in')
    check_out_str = request.GET.get('check_out')

    if not all([house_id, check_in_str, check_out_str]):
        return JsonResponse({'error': 'Укажите house_id, check_in и check_out'}, status=400)

    house = get_object_or_404(House, pk=house_id)

    try:
        check_in = date.fromisoformat(check_in_str)
        check_out = date.fromisoformat(check_out_str)
    except ValueError:
        return JsonResponse({'error': 'Неверный формат дат'}, status=400)

    if check_out <= check_in:
        return JsonResponse({'error': 'Дата выезда должна быть позже даты заезда'}, status=400)

    has_conflict = check_overlap(house, check_in, check_out)
    result = calculate_booking_price(house, check_in, check_out)
    result['has_conflict'] = has_conflict

    return JsonResponse(result)


def _send_booking_notification(booking: BookingRequest) -> None:
    if not getattr(settings, "BOOKING_NOTIFY_EMAIL", ""):
        return

    house_name = booking.house.name if booking.house else "Дом не выбран"
    total_price = f"{booking.total_price} ₽" if booking.total_price else "не рассчитана"
    message = (
        "Новая заявка на бронирование\n\n"
        f"Дом: {house_name}\n"
        f"Имя: {booking.name}\n"
        f"Телефон: {booking.phone}\n"
        f"Заезд: {booking.check_in}\n"
        f"Выезд: {booking.check_out}\n"
        f"Гостей: {booking.guests}\n"
        f"Стоимость: {total_price}\n"
        f"Комментарий: {booking.message or '-'}\n"
    )
    try:
        send_mail(
            subject=f"Новая заявка на бронирование: {house_name}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.BOOKING_NOTIFY_EMAIL],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Не удалось отправить уведомление о бронировании")


def blog_list(request):
    posts = BlogPost.objects.filter(is_published=True)
    settings = SiteSettings.load()
    return render(request, 'blog_list.html', {'posts': posts, 'settings': settings})


def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)
    settings = SiteSettings.load()
    return render(request, 'blog_detail.html', {'post': post, 'settings': settings})


# ==================== DASHBOARD ====================

def dashboard_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user and user.is_staff:
            login(request, user)
            return redirect('dashboard')
        return render(request, 'dashboard/login.html', {'error': 'Неверный логин или пароль'})
    return render(request, 'dashboard/login.html')


def dashboard_logout(request):
    logout(request)
    return redirect('dashboard_login')


@login_required(login_url='/dashboard/login/')
def dashboard(request):
    # Filters
    status_filter = request.GET.get('status', '')
    house_filter = request.GET.get('house', '')
    month_filter = request.GET.get('month', '')

    bookings = BookingRequest.objects.select_related('house').all()

    if status_filter:
        bookings = bookings.filter(status=status_filter)
    if house_filter:
        bookings = bookings.filter(house_id=house_filter)
    if month_filter:
        try:
            y, m = month_filter.split('-')
            bookings = bookings.filter(check_in__year=int(y), check_in__month=int(m))
        except ValueError:
            pass

    # Stats
    today = date.today()
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    stats = {
        'total': BookingRequest.objects.count(),
        'pending': BookingRequest.objects.filter(status='pending').count(),
        'confirmed': BookingRequest.objects.filter(status='confirmed').count(),
        'month_revenue': BookingRequest.objects.filter(
            status='confirmed', check_in__gte=month_start, check_in__lt=next_month
        ).aggregate(total=Sum('total_price'))['total'] or 0,
        'upcoming': BookingRequest.objects.filter(
            status='confirmed', check_in__gte=today
        ).count(),
    }

    houses = House.objects.all()

    return render(request, 'dashboard/index.html', {
        'bookings': bookings[:50],
        'stats': stats,
        'houses': houses,
        'status_filter': status_filter,
        'house_filter': house_filter,
        'month_filter': month_filter,
    })


@login_required(login_url='/dashboard/login/')
def dashboard_booking_action(request, booking_id):
    if request.method == 'POST':
        booking = get_object_or_404(BookingRequest, pk=booking_id)
        action = request.POST.get('action')
        if action in ('confirmed', 'rejected', 'cancelled'):
            booking.status = action
            booking.save()
            return JsonResponse({'success': True, 'status': booking.get_status_display()})
    return JsonResponse({'error': 'Invalid'}, status=400)
