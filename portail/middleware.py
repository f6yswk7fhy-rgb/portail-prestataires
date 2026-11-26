"""En-têtes HTTP de sécurité complémentaires à ceux de Django."""

CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self'; "
    "script-src 'self'; "
    "form-action 'self' https://login.microsoftonline.com; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "object-src 'none'"
)


class EntetesSecuriteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", CSP)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        if request.user.is_authenticated if hasattr(request, "user") else False:
            response.setdefault("Cache-Control", "no-store")
        return response
