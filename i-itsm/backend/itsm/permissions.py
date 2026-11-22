from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_administrator)


class IsAdministratorOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.method in SAFE_METHODS or request.user.is_administrator


class IsStaffMember(BasePermission):
    """Technicians and administrators."""
    def has_permission(self, request, view):
        user = request.user
        return bool(user.is_authenticated and (user.is_administrator or user.is_technician))
