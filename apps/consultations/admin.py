from django.contrib import admin
from apps.consultations.models import Consultation

@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'doctor', 'status', 'created_at', 'video_room_id')
    list_filter = ('status', 'created_at')
    search_fields = ('patient__email', 'doctor__user__email', 'video_room_id')
