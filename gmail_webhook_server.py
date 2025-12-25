"""
Gmail Webhook Server using Google Pub/Sub Push Notifications

This creates a real webhook that gets called immediately when emails arrive,
instead of polling every 2 minutes.
"""

import json
import base64
import hmac
import hashlib
from flask import Flask, request, jsonify
from conversation_manager import ConversationManager
import threading
import time

app = Flask(__name__)
conversation_manager = ConversationManager()

# Webhook endpoint that Gmail will call
@app.route('/gmail-webhook', methods=['POST'])
def gmail_webhook():
    """
    This function gets called by Gmail immediately when new emails arrive
    """
    try:
        # Verify the request is from Google (security)
        if not verify_webhook_signature(request):
            return 'Unauthorized', 401
        
        # Parse the incoming webhook data
        webhook_data = request.get_json()
        
        if webhook_data and 'message' in webhook_data:
            # Decode the message data
            message_data = webhook_data['message']['data']
            decoded_data = base64.b64decode(message_data).decode('utf-8')
            notification = json.loads(decoded_data)
            
            print(f"📧 Webhook triggered! New email received: {notification}")
            
            # Process the new email in a separate thread to avoid blocking
            threading.Thread(
                target=process_new_email_notification,
                args=(notification,),
                daemon=True
            ).start()
            
            return jsonify({'status': 'success'}), 200
        
        return jsonify({'status': 'no_data'}), 200
        
    except Exception as e:
        print(f"❌ Error in webhook: {e}")
        return jsonify({'error': str(e)}), 500

def verify_webhook_signature(request):
    """
    Verify that the webhook request is actually from Google
    """
    # In production, you should verify the JWT token from Google
    # For now, we'll accept all requests (you should implement proper verification)
    return True

def process_new_email_notification(notification):
    """
    Process the new email notification from Gmail
    """
    try:
        print("🔍 Processing new email notification...")
        
        # The notification contains the message ID of the new email
        if 'historyId' in notification:
            # Check for new emails and process replies
            conversation_manager.check_for_replies()
            print("✅ Email notification processed successfully")
        
    except Exception as e:
        print(f"❌ Error processing email notification: {e}")

@app.route('/webhook-status', methods=['GET'])
def webhook_status():
    """
    Health check endpoint for the webhook server
    """
    return jsonify({
        'status': 'active',
        'timestamp': time.time(),
        'message': 'Gmail webhook server is running'
    })

@app.route('/start-conversation', methods=['POST'])
def start_conversation_api():
    """
    API endpoint to start new conversations
    """
    try:
        data = request.get_json()
        email = data.get('email')
        name = data.get('name', '')
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        from conversation_manager import start_conversation_with_prospect
        message_id = start_conversation_with_prospect(email, name)
        
        if message_id:
            return jsonify({
                'status': 'success',
                'message_id': message_id,
                'email': email,
                'name': name
            })
        else:
            return jsonify({'error': 'Failed to send email'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/conversations', methods=['GET'])
def get_conversations():
    """
    API endpoint to get all conversations
    """
    try:
        conversations = conversation_manager.load_conversation_data()
        return jsonify(conversations)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Gmail Webhook Server...")
    print("📧 This server will receive immediate notifications when emails arrive")
    print("🔗 Webhook URL: http://localhost:5000/gmail-webhook")
    print("📊 Status URL: http://localhost:5000/webhook-status")
    print("🎯 API URL: http://localhost:5000/start-conversation")
    
    # Run the Flask server
    app.run(
        host='0.0.0.0',  # Allow external connections
        port=5000,
        debug=True,
        threaded=True    # Handle multiple requests simultaneously
    )
