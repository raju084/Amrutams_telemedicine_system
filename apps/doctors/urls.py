from django.urls import path
from apps.doctors.views import (
    DoctorListView,
    DoctorDetailView,
    DoctorSlotListView,
    DoctorSlotBatchCreateView,
)

urlpatterns = [
    path('', DoctorListView.as_view(), name='doctor-list'),
    path('<uuid:pk>/', DoctorDetailView.as_view(), name='doctor-detail'),
    path('<uuid:doctor_id>/slots/', DoctorSlotListView.as_view(), name='doctor-slots'),
    path('slots/batch-create/', DoctorSlotBatchCreateView.as_view(), name='doctor-slots-batch-create'),
]
