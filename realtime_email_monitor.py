import base64
import json
import time
from threading import Thread
from google.cloud import pubsub_v1
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os

class EmailMonitor:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 
                       'https://www.googleapis.com/auth/pubsub']
        self.service = None
        self.setup_gmail_service()
        
    def setup_gmail_service(self):
        """Setup Gmail API service"""
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)
        
        if not creds or not creds.valid:
            # Handle refresh or re-auth as needed
            pass
            
        self.service = build("gmail", "v1", credentials=creds)
    
    def setup_push_notifications(self, project_id, topic_name):
        """Setup Gmail push notifications"""
        try:
            # Enable push notifications for Gmail
            request = {
                'topicName': f'projects/{project_id}/topics/{topic_name}',
                'labelIds': ['INBOX']
            }
            
            result = self.service.users().watch(userId='me', body=request).execute()
            print(f"Push notifications enabled: {result}")
            return result
            
        except Exception as error:
            print(f"Error setting up push notifications: {error}")
            return None
    
    def handle_new_email(self, message_data):
        """Handle new email notification"""
        try:
            # Decode the message
            data = json.loads(base64.b64decode(message_data).decode())
            
            # Get the email details
            message_id = data.get('messageId')
            if message_id:
                email_data = self.get_email_content(message_id)
                
                # Check if this is a reply to your sent email
                if self.is_reply_to_sent_email(email_data):
                    print(f"Reply received from: {email_data['sender']}")
                    self.process_client_reply(email_data)
                    
        except Exception as error:
            print(f"Error handling new email: {error}")
    
    def is_reply_to_sent_email(self, email_data):
        """Check if the email is a reply to your sent email"""
        subject = email_data.get('subject', '').lower()
        return 'service offering' in subject or 're:' in subject
    
    def process_client_reply(self, email_data):
        """Process the client's reply - customize this function"""
        print(f"Processing reply from: {email_data['sender']}")
        print(f"Subject: {email_data['subject']}")
        print(f"Body: {email_data['body']}")
        
        # Add your custom logic here
        # For example:
        # - Analyze the reply content
        # - Send automatic response
        # - Update database
        # - Trigger other workflows
        
        # Example: Send acknowledgment
        self.send_acknowledgment(email_data['sender'])
    
    def send_acknowledgment(self, recipient_email):
        """Send automatic acknowledgment"""
        # Use your existing email sending function
        print(f"Sending acknowledgment to {recipient_email}")
        # Implementation would use your gmail_send_message function
    
    def get_email_content(self, message_id):
        """Get email content by message ID"""
        # Use your existing get_email_content function
        return get_email_content(self.service, message_id)