from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm
from apps.users.models import User, PatientProfile


class EmailUserCreationForm(UserCreationForm):
    """Custom creation form that uses email instead of username."""
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email', 'first_name', 'last_name', 'role')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = EmailUserCreationForm

    list_display = ('email', 'first_name', 'last_name', 'role', 'is_verified', 'mfa_enabled', 'is_staff')
    list_filter = ('role', 'is_verified', 'mfa_enabled', 'is_staff')
    ordering = ('email',)

    # Fieldsets for editing an existing user
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Role & Permissions', {'fields': ('role', 'is_verified', 'mfa_enabled', 'is_active', 'is_staff', 'is_superuser')}),
    )

    # Fieldsets for the "Add user" page — no username field
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )

    search_fields = ('email', 'first_name', 'last_name')


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'date_of_birth', 'gender', 'blood_group', 'prakriti')
    search_fields = ('user__email', 'emergency_contact')
