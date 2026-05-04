from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import House, BlogPost


class MainSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"

    def items(self):
        static_pages = ["index", "booking_page", "blog_list"]
        house_pages = list(House.objects.values_list("slug", flat=True))
        return [*static_pages, *house_pages]

    def location(self, item):
        if item in {"index", "booking_page", "blog_list"}:
            return reverse(item)
        return reverse("house_detail", kwargs={"slug": item})

    def priority(self, item):
        if item == "index":
            return 1.0
        if item == "booking_page":
            return 0.9
        if item == "blog_list":
            return 0.7
        return 0.8


class BlogSitemap(Sitemap):
    protocol = "https"
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return BlogPost.objects.filter(is_published=True)

    def location(self, post):
        return reverse("blog_detail", kwargs={"slug": post.slug})

    def lastmod(self, post):
        return post.published_date
