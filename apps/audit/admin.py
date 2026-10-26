from django.contrib import admin
from apps.audit.models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user_email', 'user_role', 'action', 'resource_type', 'ip_address')
    list_filter = ('action', 'resource_type', 'user_role')
    search_fields = ('user_email', 'resource_id', 'correlation_id')
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
