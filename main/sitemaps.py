from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import House


class MainSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        static_pages = ["index", "booking_page"]
        house_pages = list(House.objects.values_list("slug", flat=True))
        return [*static_pages, *house_pages]

    def location(self, item):
        if item in {"index", "booking_page"}:
            return reverse(item)
        return reverse("house_detail", kwargs={"slug": item})

    def priority(self, item):
        if item == "index":
            return 1.0
        if item == "booking_page":
            return 0.9
        return 0.8
