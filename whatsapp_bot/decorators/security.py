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

    # Log signatures for debugging
    logging.info(f"Received signature: {signature}")
    logging.info(f"Expected signature: {expected_signature}")
    
    return hmac.compare_digest(expected_signature, signature)

def signature_required(view_func):
    """
    Security guard decorator for webhook endpoints
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        # Allow GET requests without signature check (for initial webhook verification)
        if request.method == 'GET':
            return view_func(request, *args, **kwargs)

        # Get the signature from request headers (remove 'sha256=' prefix)
        signature_header = request.headers.get("X-Hub-Signature-256", "")
        logging.info(f"Received signature header: {signature_header}")
        
        if not signature_header:
            logging.warning("No signature header found")
            return JsonResponse(
                {"status": "error", "message": "No signature provided"}, 
                status=403
            )

        signature = signature_header[7:] if signature_header.startswith("sha256=") else signature_header
        
        # Get the raw body
        payload = request.body
        
        # Check if signature is valid
        if not validate_signature(payload, signature):
            logging.warning("Signature verification failed!")
            return JsonResponse(
                {"status": "error", "message": "Invalid signature"}, 
                status=403
            )
        
        # If signature is valid, process the request
        return view_func(request, *args, **kwargs)

    return wrapped_view