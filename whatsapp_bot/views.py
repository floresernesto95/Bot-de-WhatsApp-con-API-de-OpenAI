from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .decorators.security import signature_required
from .utils.whatsapp_message_processor import process_whatsapp_message, is_valid_whatsapp_message
import json
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@signature_required
def webhook_receive(request):
    """Handle both GET verification and POST messages"""
    if request.method == 'GET':
        # Handle verification
        logging.info("GET request received at /webhook")
        
        # Get verification parameters from WhatsApp
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        
        verify_token = settings.WHATSAPP_CONFIG['VERIFY_TOKEN']

        if mode and token:
            if mode == "subscribe" and token == verify_token:
                logging.info("WEBHOOK_VERIFIED")
                return HttpResponse(challenge)
            else:
                logging.warning("VERIFICATION_FAILED")
                return JsonResponse(
                    {"status": "error", "message": "Verification failed"}, 
                    status=403
                )
        
        logging.warning("MISSING_PARAMETER")
        return JsonResponse(
            {"status": "error", "message": "Missing parameters"}, 
            status=400
        )
        
    elif request.method == 'POST':
        # Handle incoming messages
        logging.info("POST request received at /webhook")
        
        try:
            # Parse the JSON body
            body = json.loads(request.body.decode('utf-8'))
            logging.info(f"Received webhook body: {json.dumps(body, indent=2)}")

            # Check if this is a status update
            status_update = (
                body.get("entry", [{}])[0]
                .get("changes", [{}])[0]
                .get("value", {})
                .get("statuses")
            )
            
            if status_update:
                logging.info("Received a WhatsApp status update.")
                return JsonResponse({"status": "ok"})

            # Process valid WhatsApp messages
            if is_valid_whatsapp_message(body):
                logging.info("Valid WhatsApp message received. Processing...")
                process_whatsapp_message(body)
                return JsonResponse({"status": "ok"})
            else:
                logging.warning("Not a valid WhatsApp API event")
                return JsonResponse(
                    {"status": "error", "message": "Not a WhatsApp API event"},
                    status=404
                )

        except json.JSONDecodeError:
            logging.error("Failed to decode JSON")
            return JsonResponse(
                {"status": "error", "message": "Invalid JSON provided"},
                status=400
            )
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return JsonResponse(
                {"status": "error", "message": "Internal server error"},
                status=500
            )