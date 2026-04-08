from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.db.models import Sum, Count, Q
from .models import SiteSettings, House, Activity, SectionDivider, RouteCity, GalleryImage, BookingRequest
from .forms import BookingForm
from .pricing import calculate_booking_price, get_booked_dates, get_prices_map, check_overlap


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
