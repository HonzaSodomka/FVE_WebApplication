# backend/api/auth.py

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.urls import resolve
import json
import logging

logger = logging.getLogger('api')

# Globální heslo pro přístup k aplikaci
ACCESS_PASSWORD = "FVE.Bakalarka.2025"

@csrf_exempt
@require_http_methods(["POST"])
def verify_password(request):
    """View pro ověření hesla"""
    try:
        data = json.loads(request.body)
        password = data.get('password')

        if password == ACCESS_PASSWORD:
            request.session['is_verified'] = True
            return JsonResponse({'message': 'OK'})
        else:
            return JsonResponse({'error': 'Nesprávné heslo'}, status=401)
            
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return JsonResponse({'error': 'Chyba při ověření'}, status=500)

@require_http_methods(["GET"])
def check_access(request):
    """View pro kontrolu přístupu"""
    is_verified = request.session.get('is_verified', False)
    return JsonResponse({'hasAccess': is_verified})

class SimpleAuthMiddleware:
    """Middleware pro kontrolu přístupu ke všem API endpointům"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Seznam cest, které nevyžadují autentizaci
        public_paths = [
            'verify_password',
            'check_access',
        ]

        # Získání názvu aktuální cesty
        current_url_name = resolve(request.path_info).url_name
        is_verified = request.session.get('is_verified', False)

        # Kontrola přístupu
        if current_url_name not in public_paths and not is_verified:
            return JsonResponse({
                'error': 'Unauthorized',
                'detail': 'Pro přístup je vyžadováno heslo'
            }, status=401)

        return self.get_response(request)