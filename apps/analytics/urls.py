from django.urls import path
from apps.analytics.views import AdminAnalyticsOverviewView

urlpatterns = [
    path('overview/', AdminAnalyticsOverviewView.as_view(), name='analytics-overview'),
]
