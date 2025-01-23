# NEW!!! - Set up URLs
from django.urls import path
from . import views

app_name = 'whatsapp_bot'

urlpatterns = [
    # Single path that handles both GET and POST
    path('webhook/', views.webhook_receive, name='webhook'),
]