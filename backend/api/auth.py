"""
Autentizační modul pro API s jednoduchým ověřením hesla a middleware pro kontrolu přístupu.
"""
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.urls import resolve
import json
import logging
from typing import Callable, List

logger = logging.getLogger('api')

# Globální heslo pro přístup k aplikaci
ACCESS_PASSWORD = "FVE.Bakalarka.2025"


@csrf_exempt
@require_http_methods(["POST"])
def verify_password(request: HttpRequest) -> JsonResponse:
    """
    View pro ověření hesla.
    
    Args:
        request: HTTP požadavek obsahující heslo v těle
        
    Returns:
        JsonResponse s úspěchem nebo chybou
    """
    try:
        data = json.loads(request.body)
        password = data.get('password')

        if password == ACCESS_PASSWORD:
            request.session['is_verified'] = True
            return JsonResponse({'message': 'OK'})
        else:
            logger.warning("Neúspěšný pokus o přihlášení")
            return JsonResponse({'error': 'Nesprávné heslo'}, status=401)
            
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return JsonResponse({'error': 'Chyba při ověření'}, status=500)


@require_http_methods(["GET"])
def check_access(request: HttpRequest) -> JsonResponse:
    """
    View pro kontrolu přístupu.
    
    Args:
        request: HTTP požadavek
        
    Returns:
        JsonResponse s informací o stavu přístupu
    """
    is_verified = request.session.get('is_verified', False)
    return JsonResponse({'hasAccess': is_verified})


class SimpleAuthMiddleware:
    """
    Middleware pro kontrolu přístupu ke všem API endpointům.
    Nedovolí přístup k zabezpečeným cestám bez ověření.
    """
    
    def __init__(self, get_response: Callable):
        """
        Inicializace middleware.
        
        Args:
            get_response: Další middleware nebo view v řetězci zpracování
        """
        self.get_response = get_response
        # Seznam cest, které nevyžadují autentizaci
        self.public_paths: List[str] = [
            'verify_password',
            'check_access',
        ]

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Zpracování požadavku a kontrola přístupu.
        
        Args:
            request: HTTP požadavek
            
        Returns:
            HTTP odpověď
        """
        # Získání názvu aktuální cesty
        current_url_name = resolve(request.path_info).url_name
        is_verified = request.session.get('is_verified', False)
        
        # Kontrola přístupu
        if current_url_name not in self.public_paths and not is_verified:
            logger.warning(f"Neautorizovaný přístup k {request.path_info}")
            return JsonResponse({
                'error': 'Unauthorized',
                'detail': 'Pro přístup je vyžadováno heslo'
            }, status=401)
        
        return self.get_response(request)