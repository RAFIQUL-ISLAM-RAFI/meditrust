from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def error_page(request, text, status=403):
    return render(request, 'ui/error.html', {'error': text}, status=status)


def role_required(role):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.user.role != role:
                return error_page(request, 'Your account cannot access this portal.')
            if not request.user.is_verified:
                return render(request, 'ui/pending.html', status=403)
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
