from django.contrib import admin
from apps.prescriptions.models import Prescription, PrescriptionItem

class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 1

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'consultation', 'signature_timestamp', 'digital_signature')
    inlines = [PrescriptionItemInline]
