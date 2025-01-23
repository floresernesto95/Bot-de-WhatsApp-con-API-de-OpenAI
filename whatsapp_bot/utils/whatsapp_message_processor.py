from django.http import JsonResponse
from django.conf import settings
from whatsapp_bot.services.openai_service import generate_response, clear_conversation_history
import re
import logging
import json
import requests
import time

# Dictionary to store processed messages to prevent duplicates
processed_messages = {}

def is_duplicate_message(message_id, timestamp, expiration_time=300):
    """
    Check if a message was already processed to prevent duplicate handling
    Messages expire after 5 minutes (300 seconds)
    """
    current_time = time.time()
    
    # Clean up old messages from memory
    global processed_messages
    processed_messages = {id: ts for id, ts in processed_messages.items() if current_time - ts < expiration_time}
    
    # Check if message was already processed
    if message_id in processed_messages:
        return True
    
    # If not processed, add to tracking
    processed_messages[message_id] = current_time
    return False

def log_http_response(response):
    """Log details of HTTP responses for debugging"""
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")

def get_text_message_input(recipient, text):
    """
    Format message data for WhatsApp API
    Creates the JSON structure WhatsApp expects
    """
    logging.info(f"Preparing message for recipient {recipient}: {text[:50]}...")
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

def send_message(data):
    """
    Send message to WhatsApp using their API
    Handles errors and timeouts
    """
    logging.info("Attempting to send message")
    access_token = settings.WHATSAPP_CONFIG['ACCESS_TOKEN']
    phone_number_id = settings.WHATSAPP_CONFIG['PHONE_NUMBER_ID']
    version = settings.WHATSAPP_CONFIG['VERSION']

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    url = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"

    try:
        response = requests.post(url, data=data, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return JsonResponse({"status": "error", "message": "Request timed out"}, status=408)
    except requests.RequestException as e:
        logging.error(f"Request failed due to: {e}")
        return JsonResponse({"status": "error", "message": "Failed to send message"}, status=500)
    else:
        logging.info("Message sent successfully")
        log_http_response(response)
        return response

def process_text_for_whatsapp(text):
    """
    Format text to be WhatsApp-friendly:
    - Remove bracketed content
    - Convert markdown-style bold (**) to WhatsApp-style bold (*)
    """
    # Remove brackets and their content
    pattern = r"\【.*?\】"
    text = re.sub(pattern, "", text).strip()

    # Convert markdown bold to WhatsApp bold
    pattern = r"\*\*(.*?)\*\*"
    replacement = r"*\1*"
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text

def process_whatsapp_message(body):
    """
    Main function to handle incoming WhatsApp messages:
    1. Extract sender info
    2. Check for duplicates
    3. Generate response using OpenAI
    4. Format and send response
    """
    logging.info("Processing WhatsApp message")
    try:
        # Get sender information
        wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
        name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
        logging.info(f"Message from: {name} (WA ID: {wa_id})")

        # Get message details
        message = body["entry"][0]["changes"][0]["value"]["messages"][0]
        message_id = message["id"]
        timestamp = int(message["timestamp"])
        
        # Check for duplicate message
        if is_duplicate_message(message_id, timestamp):
            logging.info(f"Duplicate message detected. Ignoring message with ID: {message_id}")
            return JsonResponse({"status": "ok", "message": "Duplicate message ignored"})

        # Process message and generate response
        message_body = message["text"]["body"]
        logging.info(f"Received message: {message_body}")

        # Check for reset command
        if message_body.lower().strip() in ["reset", "clear", "/reset", "/clear"]:
            clear_conversation_history(wa_id)
            response = "Conversation history has been cleared. How can I help you today?"
        else:
            # Generate and format response
            response = generate_response(message_body, wa_id, name)

        # Generate and format response
        # response = generate_response(message_body, wa_id, name)
        response = process_text_for_whatsapp(response)
        logging.info(f"Generated response: {response[:50]}...")

        # Send response back to user
        data = get_text_message_input(wa_id, response)
        send_message(data)
        
        return JsonResponse({"status": "ok"})

    except KeyError as e:
        logging.error(f"Invalid message format: {e}")
        return JsonResponse(
            {"status": "error", "message": "Invalid message format"}, 
            status=400
        )
    except Exception as e:
        logging.error(f"Error processing message: {e}")
        return JsonResponse(
            {"status": "error", "message": "Internal server error"}, 
            status=500
        )

def is_valid_whatsapp_message(body):
    """
    Verify if the received message has all required WhatsApp fields
    This prevents processing invalid or malformed messages
    """
    logging.info("Validating WhatsApp message structure")
    is_valid = (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )
    logging.info(f"Message is valid: {is_valid}")
    return is_valid