from django.contrib import admin
from apps.consultations.models import Consultation
from apps.users.models import User

@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'doctor', 'status', 'created_at', 'video_room_id')
    list_filter = ('status', 'created_at')
    search_fields = ('patient__email', 'doctor__user__email', 'video_room_id')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'patient':
            kwargs['queryset'] = User.objects.filter(role=User.ROLE_PATIENT)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
