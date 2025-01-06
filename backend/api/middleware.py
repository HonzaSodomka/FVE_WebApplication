# api/middleware.py
from django.http import HttpResponseForbidden
import logging

logger = logging.getLogger('api')

class SecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Jen kontrola hosta
        if request.get_host() != 'bijec.nti.tul.cz':
            logger.warning(f"Blocked request from unauthorized host: {request.get_host()}")
            return HttpResponseForbidden("Access denied")

        return self.get_response(request)