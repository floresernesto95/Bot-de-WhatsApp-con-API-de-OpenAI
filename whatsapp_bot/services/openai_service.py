from django.conf import settings
from openai import OpenAI
from whatsapp_bot.models import Conversation, Message
from django.utils import timezone
from django.db import transaction
import logging
import os

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_CONFIG['API_KEY'])

MAX_CONTEXT_MESSAGES = 10  # Adjust this to control how many previous messages to include


def get_conversation_messages(conversation, include_system=True):
    """Get the recent message history for a conversation"""
    messages = []
    
    # Always include the system message
    if include_system:
        messages.append({
            "role": "system",
            "content": settings.OPENAI_CONFIG['SYSTEM_PROMPT']
        })
    
    # Get recent messages
    recent_messages = conversation.messages.all().order_by('-timestamp')[:MAX_CONTEXT_MESSAGES]
    
    # Add them in chronological order
    for message in reversed(recent_messages):
        messages.append({
            "role": message.role,
            "content": message.content
        })
    
    return messages

@transaction.atomic
def generate_response(message_body, wa_id, name):
    """
    Generate a response using OpenAI's chat completion API
    and maintain conversation history
    """
    try:
        # Get or create conversation
        conversation, created = Conversation.objects.get_or_create(
            wa_id=wa_id,
            defaults={'name': name}
        )
        
        # If not created but name changed, update it
        if not created and conversation.name != name:
            conversation.name = name
            conversation.save()

        # Store user message
        Message.objects.create(
            conversation=conversation,
            role='user',
            content=message_body
        )

        # Get conversation history
        messages = get_conversation_messages(conversation)
        
        # Add the new user message
        messages.append({
            "role": "user",
            "content": message_body
        })

        # Create the chat completion request
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.1,
            max_tokens=500
        )
        
        # Extract the response
        new_message = completion.choices[0].message.content
        
        # Store assistant's response
        Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=new_message
        )

        logging.info(f"Generated message: {new_message}")
        return new_message

    except Exception as e:
        logging.error(f"Error generating response: {str(e)}")
        return "I apologize, but I'm having trouble processing your request right now. Please try again later."
    
@transaction.atomic
def clear_conversation_history(wa_id):
    """
    Clear the conversation history for a specific WhatsApp ID
    but maintain the conversation record
    """
    try:
        conversation = Conversation.objects.get(wa_id=wa_id)
        # Delete all messages but keep the conversation record
        conversation.messages.all().delete()
        # Add a system message noting the conversation reset
        Message.objects.create(
            conversation=conversation,
            role='system',
            content='Conversation history cleared by user'
        )
        logging.info(f"Cleared conversation history for wa_id: {wa_id}")
    except Conversation.DoesNotExist:
        logging.warning(f"No conversation found for wa_id: {wa_id}")