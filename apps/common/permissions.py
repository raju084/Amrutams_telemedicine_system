from rest_framework import permissions

class IsPatient(permissions.BasePermission):
    """
    Allows access only to authenticated users with PATIENT role.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'PATIENT')


class IsDoctor(permissions.BasePermission):
    """
    Allows access only to authenticated users with DOCTOR role.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'DOCTOR')


class IsAdminUserRole(permissions.BasePermission):
    """
    Allows access to users with ADMIN role or Django is_staff/is_superuser.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and 
            (request.user.role == 'ADMIN' or request.user.is_staff or request.user.is_superuser)
        )


class IsAuditor(permissions.BasePermission):
    """
    Allows access to compliance auditors and administrators.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and 
            (request.user.role in ('AUDITOR', 'ADMIN') or request.user.is_superuser)
        )


class IsOwnerOrDoctorOrAdmin(permissions.BasePermission):
    """
    Allows patient owner, consulting doctor, or admin to access resource.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == 'ADMIN' or request.user.is_staff:
            return True
        if hasattr(obj, 'patient_id') and obj.patient_id == request.user.id:
            return True
        if hasattr(obj, 'doctor') and hasattr(obj.doctor, 'user_id') and obj.doctor.user_id == request.user.id:
            return True
        if hasattr(obj, 'user_id') and obj.user_id == request.user.id:
            return True
        return False
