"""
Gmail Push Notification Setup

This script sets up Gmail Push Notifications so your webhook gets called
immediately when new emails arrive, instead of polling every 2 minutes.
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# You need to add pubsub scope for push notifications
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/pubsub'
]

class GmailPushSetup:
    def __init__(self):
        self.service = None
        self.pubsub_service = None
        
    def authenticate(self):
        """Authenticate Gmail and Pub/Sub services"""
        creds = None
        if os.path.exists('token_webhook.json'):
            creds = Credentials.from_authorized_user_file('token_webhook.json', SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open('token_webhook.json', 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('gmail', 'v1', credentials=creds)
        self.pubsub_service = build('pubsub', 'v1', credentials=creds)
        return True

    def setup_push_notifications(self, webhook_url, project_id):
        """
        Set up Gmail Push Notifications
        
        Args:
            webhook_url: Your webhook URL (e.g., 'https://yourserver.com/gmail-webhook')
            project_id: Your Google Cloud Project ID
        """
        try:
            # Create topic name
            topic_name = f"projects/{project_id}/topics/gmail-notifications"
            
            print(f"🔧 Setting up push notifications...")
            print(f"📧 Gmail will send notifications to: {webhook_url}")
            print(f"📂 Using topic: {topic_name}")
            
            # Set up the watch request
            watch_request = {
                'topicName': topic_name,
                'labelIds': ['INBOX'],  # Monitor inbox
                'labelFilterAction': 'include'
            }
            
            # Start watching for changes
            result = self.service.users().watch(
                userId='me',
                body=watch_request
            ).execute()
            
            print("✅ Gmail Push Notifications setup successful!")
            print(f"📋 Watch Details:")
            print(f"   - History ID: {result.get('historyId')}")
            print(f"   - Expiration: {result.get('expiration')}")
            
            return result
            
        except HttpError as error:
            print(f"❌ Error setting up push notifications: {error}")
            return None

    def stop_push_notifications(self):
        """Stop Gmail Push Notifications"""
        try:
            result = self.service.users().stop(userId='me').execute()
            print("⏹️  Gmail Push Notifications stopped")
            return result
        except HttpError as error:
            print(f"❌ Error stopping notifications: {error}")
            return None

def create_pubsub_topic_and_subscription(project_id, webhook_url):
    """
    Create Pub/Sub topic and subscription for Gmail notifications
    This needs to be run once to set up the infrastructure
    """
    
    instructions = f"""
🔧 GMAIL WEBHOOK SETUP INSTRUCTIONS

To use real webhooks instead of polling, you need to:

1. **Enable Google Cloud Pub/Sub API**:
   - Go to Google Cloud Console
   - Enable "Cloud Pub/Sub API"

2. **Create Pub/Sub Topic**:
   ```bash
   gcloud pubsub topics create gmail-notifications
   ```

3. **Create Push Subscription**:
   ```bash
   gcloud pubsub subscriptions create gmail-webhook-subscription \\
     --topic=gmail-notifications \\
     --push-endpoint={webhook_url}
   ```

4. **Grant Gmail permissions to publish**:
   ```bash
   gcloud pubsub topics add-iam-policy-binding gmail-notifications \\
     --member=serviceAccount:gmail-api-push@system.gserviceaccount.com \\
     --role=roles/pubsub.publisher
   ```

5. **Run the webhook server**:
   ```bash
   python gmail_webhook_server.py
   ```

6. **Setup Gmail watch**:
   ```bash
   python gmail_push_setup.py
   ```

🌐 **For Local Development**:
   - Use ngrok to expose local server: `ngrok http 5000`
   - Use the ngrok URL as your webhook_url

📝 **Your Project ID**: {project_id}
🔗 **Your Webhook URL**: {webhook_url}
"""
    
    print(instructions)

if __name__ == "__main__":
    print("📧 Gmail Push Notification Setup")
    print("=" * 50)
    
    # Get user input
    project_id = input("Enter your Google Cloud Project ID: ").strip()
    webhook_url = input("Enter your webhook URL (e.g., https://yourserver.com/gmail-webhook): ").strip()
    
    if not project_id or not webhook_url:
        print("❌ Project ID and Webhook URL are required")
        exit()
    
    # Show setup instructions
    create_pubsub_topic_and_subscription(project_id, webhook_url)
    
    # Ask if user wants to proceed with Gmail watch setup
    proceed = input("\nHave you completed the Pub/Sub setup above? (y/n): ").lower().strip()
    
    if proceed == 'y':
        setup = GmailPushSetup()
        if setup.authenticate():
            result = setup.setup_push_notifications(webhook_url, project_id)
            if result:
                print("\n🎉 Setup complete! Your webhook will now receive immediate notifications.")
            else:
                print("\n❌ Setup failed. Please check your configuration.")
    else:
        print("\n📋 Please complete the Pub/Sub setup first, then run this script again.")
