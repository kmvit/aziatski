from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('house/<slug:slug>/', views.house_detail, name='house_detail'),
    path('booking/', views.booking_page, name='booking_page'),
    path('booking/create/', views.booking_create, name='booking_create'),
    path('api/calendar/<int:house_id>/', views.api_calendar_data, name='api_calendar'),
    path('api/price/', views.api_calculate_price, name='api_calculate_price'),
    # Blog
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/login/', views.dashboard_login, name='dashboard_login'),
    path('dashboard/logout/', views.dashboard_logout, name='dashboard_logout'),
    path('dashboard/booking/<int:booking_id>/action/', views.dashboard_booking_action, name='dashboard_booking_action'),
]
