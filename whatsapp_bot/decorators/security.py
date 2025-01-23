from functools import wraps
from django.http import JsonResponse
from django.conf import settings
import logging
import hashlib
import hmac

def validate_signature(payload, signature):
    """
    Security check: Verify that incoming messages are really from WhatsApp
    """
    app_secret = settings.WHATSAPP_CONFIG['APP_SECRET']
    
    # Create the expected signature using our app secret
    expected_signature = hmac.new(
        bytes(app_secret, "latin-1"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Securely compare the signatures
    return hmac.compare_digest(expected_signature, signature)

def signature_required(view_func):
    """
    Security guard decorator for webhook endpoints
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        # Get the signature from request headers (remove 'sha256=' prefix)
        signature = request.headers.get("X-Hub-Signature-256", "")[7:]
        
        # Get the raw body
        payload = request.body
        
        # Check if signature is valid
        if not validate_signature(payload, signature):
            logging.info("Signature verification failed!")
            return JsonResponse(
                {"status": "error", "message": "Invalid signature"}, 
                status=403
            )
        
        # If signature is valid, process the request
        return view_func(request, *args, **kwargs)

    return wrapped_view