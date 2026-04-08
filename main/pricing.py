from datetime import date, timedelta
from .models import House, HolidaySurcharge, BookingRequest


def get_price_for_date(house, d):
    """Return (price, label) for a specific date and house."""
    # Check holiday surcharges: house-specific first, then global, by priority
    surcharges = HolidaySurcharge.objects.filter(
        date_from__lte=d, date_to__gte=d, is_active=True
    ).filter(
        models_house_q(house)
    ).order_by('house', '-order')  # house-specific (not null) first

    for s in surcharges:
        if s.price_override:
            return s.price_override, s.name
        if s.percentage_markup:
            base = _base_price(house, d)
            return int(base * (100 + s.percentage_markup) / 100), s.name

    # No surcharge — use base pricing
    is_weekend = d.weekday() in (5, 6)
    if is_weekend and house.weekend_price:
        return house.weekend_price, 'weekend'
    return house.price_per_night, 'weekday'


def models_house_q(house):
    """Q filter for house-specific or global surcharges."""
    from django.db.models import Q
    return Q(house=house) | Q(house__isnull=True)


def _base_price(house, d):
    is_weekend = d.weekday() in (5, 6)
    if is_weekend and house.weekend_price:
        return house.weekend_price
    return house.price_per_night


def calculate_booking_price(house, check_in, check_out):
    """Calculate full price breakdown for a booking."""
    nights = []
    current = check_in
    while current < check_out:
        price, label = get_price_for_date(house, current)
        nights.append({
            'date': current.isoformat(),
            'price': price,
            'label': label,
            'is_weekend': current.weekday() in (5, 6),
        })
        current += timedelta(days=1)

    # Group by label for breakdown
    groups = {}
    for n in nights:
        key = n['label']
        if key not in groups:
            groups[key] = {'label': key, 'count': 0, 'price_per_night': n['price'], 'subtotal': 0}
        groups[key]['count'] += 1
        groups[key]['subtotal'] += n['price']

    # Prettify labels
    label_names = {'weekday': 'Будние дни', 'weekend': 'Выходные'}
    breakdown = []
    for g in groups.values():
        breakdown.append({
            'label': label_names.get(g['label'], g['label']),
            'count': g['count'],
            'price_per_night': g['price_per_night'],
            'subtotal': g['subtotal'],
        })

    total = sum(n['price'] for n in nights)
    return {
        'nights': nights,
        'breakdown': breakdown,
        'total_nights': len(nights),
        'total_price': total,
    }


def get_booked_dates(house, months_ahead=4):
    """Return list of date strings blocked by confirmed bookings."""
    today = date.today()
    end = today + timedelta(days=months_ahead * 30)
    bookings = BookingRequest.objects.filter(
        house=house, status='confirmed',
        check_out__gte=today, check_in__lte=end,
    )
    dates = set()
    for b in bookings:
        current = max(b.check_in, today)
        while current < b.check_out:
            dates.add(current.isoformat())
            current += timedelta(days=1)
    return sorted(dates)


def get_prices_map(house, months_ahead=4):
    """Return dict of date_str -> price for calendar display."""
    today = date.today()
    end = today + timedelta(days=months_ahead * 30)
    prices = {}
    holidays = {}
    current = today
    while current <= end:
        price, label = get_price_for_date(house, current)
        prices[current.isoformat()] = price
        if label not in ('weekday', 'weekend'):
            holidays[current.isoformat()] = label
        current += timedelta(days=1)
    return prices, holidays


def check_overlap(house, check_in, check_out, exclude_id=None):
    """Check if dates overlap with confirmed bookings."""
    qs = BookingRequest.objects.filter(
        house=house, status='confirmed',
        check_in__lt=check_out, check_out__gt=check_in,
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()
