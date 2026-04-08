from datetime import datetime
from .models import SiteSettings


def site_context(request):
    return {
        'settings': SiteSettings.load(),
        'current_year': datetime.now().year,
    }
