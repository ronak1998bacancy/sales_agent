"""
Simple Local Webhook Server for Gmail Notifications

This creates a local webhook server that can receive Gmail notifications.
Use with ngrok to expose it to the internet for testing.
"""

from flask import Flask, request, jsonify
import json
import threading
import time
from datetime import datetime
from conversation_manager import ConversationManager

app = Flask(__name__)
conversation_manager = ConversationManager()

# Store recent notifications to avoid duplicates
recent_notifications = []

@app.route('/gmail-webhook', methods=['POST'])
def gmail_webhook():
    """
    Webhook endpoint that gets called when Gmail sends notifications
    """
    try:
        print(f"\n🔔 Webhook called at {datetime.now()}")
        
        # Get the webhook data
        data = request.get_data()
        headers = dict(request.headers)
        
        print(f"📨 Headers: {headers}")
        print(f"📝 Data: {data}")
        
        # Process in background thread
        threading.Thread(
            target=process_gmail_notification,
            daemon=True
        ).start()
        
        return jsonify({'status': 'received'}), 200
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/manual-check', methods=['POST'])
def manual_check():
    """
    Manual endpoint to trigger email checking
    """
    try:
        print("🔍 Manual check triggered...")
        
        # Process in background thread
        threading.Thread(
            target=process_gmail_notification,
            daemon=True
        ).start()
        
        return jsonify({'status': 'checking'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def process_gmail_notification():
    """
    Process Gmail notification and check for new replies
    """
    try:
        print("🔍 Checking for new emails...")
        conversation_manager.check_for_replies()
        print("✅ Email check completed")
        
    except Exception as e:
        print(f"❌ Error processing notification: {e}")

@app.route('/status', methods=['GET'])
def status():
    """
    Health check endpoint
    """
    return jsonify({
        'status': 'active',
        'timestamp': datetime.now().isoformat(),
        'message': 'Gmail webhook server is running'
    })

@app.route('/conversations', methods=['GET'])
def get_conversations():
    """
    Get all conversations
    """
    try:
        conversations = conversation_manager.load_conversation_data()
        return jsonify(conversations)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/start-conversation', methods=['POST'])
def start_conversation():
    """
    Start a new conversation via API
    """
    try:
        data = request.get_json()
        email = data.get('email')
        name = data.get('name', '')
        
        if not email:
            return jsonify({'error': 'Email required'}), 400
        
        from conversation_manager import start_conversation_with_prospect
        message_id = start_conversation_with_prospect(email, name)
        
        if message_id:
            return jsonify({
                'status': 'success',
                'message_id': message_id,
                'email': email
            })
        else:
            return jsonify({'error': 'Failed to send email'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/', methods=['GET'])
def home():
    """
    Simple home page with instructions
    """
    html = """
    <html>
    <head><title>Gmail Webhook Server</title></head>
    <body>
        <h1>📧 Gmail Webhook Server</h1>
        <p>Status: <strong>Running</strong></p>
        
        <h2>🔗 Endpoints:</h2>
        <ul>
            <li><code>POST /gmail-webhook</code> - Gmail notification endpoint</li>
            <li><code>POST /manual-check</code> - Manual email check</li>
            <li><code>GET /conversations</code> - View all conversations</li>
            <li><code>POST /start-conversation</code> - Start new conversation</li>
            <li><code>GET /status</code> - Server status</li>
        </ul>
        
        <h2>🧪 Test Manual Check:</h2>
        <button onclick="fetch('/manual-check', {method: 'POST'}).then(r => alert('Check triggered!'))">
            Trigger Manual Check
        </button>
        
        <h2>📊 View Conversations:</h2>
        <button onclick="window.open('/conversations', '_blank')">
            View Conversations JSON
        </button>
        
        <script>
            // Auto-refresh page every 30 seconds
            setTimeout(() => location.reload(), 30000);
        </script>
    </body>
    </html>
    """
    return html

if __name__ == '__main__':
    print("🚀 Starting Simple Gmail Webhook Server...")
    print("=" * 50)
    print("📍 Server will run on: http://localhost:5000")
    print("🏠 Home page: http://localhost:5000")
    print("🔔 Webhook endpoint: http://localhost:5000/gmail-webhook")
    print("🧪 Manual check: http://localhost:5000/manual-check")
    print("📊 Conversations: http://localhost:5000/conversations")
    print()
    print("🌐 For external access (required for real webhooks):")
    print("   1. Install ngrok: https://ngrok.com/")
    print("   2. Run: ngrok http 5000")
    print("   3. Use the ngrok URL for webhook setup")
    print()
    print("⚡ For quick testing, use the manual check endpoint")
    print("=" * 50)
    
    # Run the server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )
