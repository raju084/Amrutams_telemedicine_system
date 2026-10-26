from django.contrib import admin
from apps.doctors.models import Doctor, AvailabilitySlot

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('user', 'license_number', 'specialization', 'experience_years', 'consultation_fee', 'rating', 'is_verified')
    list_filter = ('specialization', 'is_verified')
    search_fields = ('user__email', 'license_number', 'user__first_name', 'user__last_name')

@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'date', 'start_time', 'end_time', 'status', 'locked_at')
    list_filter = ('status', 'date')
    search_fields = ('doctor__user__email',)
