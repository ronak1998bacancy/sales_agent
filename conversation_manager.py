import base64
import json
import os
import time
from datetime import datetime
from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

class ConversationManager:
    def __init__(self):
        self.service = None
        self.conversation_data_file = "conversation_tracking.json"
        self.max_cycles = 4
        
    def authenticate_gmail(self):
        """Authenticate and return Gmail service"""
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('gmail', 'v1', credentials=creds)
        return self.service

    def load_conversation_data(self):
        """Load existing conversation tracking data"""
        if os.path.exists(self.conversation_data_file):
            with open(self.conversation_data_file, 'r') as f:
                return json.load(f)
        return {}

    def save_conversation_data(self, data):
        """Save conversation tracking data"""
        with open(self.conversation_data_file, 'w') as f:
            json.dump(data, f, indent=2)

    def send_service_offering_email(self, recipient_email, recipient_name=""):
        """Send initial service offering email"""
        if not self.service:
            self.authenticate_gmail()
        
        # Create personalized service offering
        subject = f"Transform Your Business with Custom Software Solutions"
        
        body = f"""Hi {recipient_name if recipient_name else 'there'},

I hope this email finds you well!

I'm Dipak from Bacancy Technology, and I wanted to reach out because I believe we can help accelerate your business growth through custom software solutions.

🚀 What we offer:
• Custom Web & Mobile App Development
• AI/ML Integration Solutions
• Cloud Migration & DevOps Services
• E-commerce Development
• Enterprise Software Solutions

💡 Why choose us:
• 10+ years of experience
• 500+ successful projects
• Dedicated development teams
• Agile methodology
• 24/7 support

I'd love to learn more about your current challenges and discuss how we can help. Would you be interested in a brief 15-minute call this week to explore potential opportunities?

Looking forward to hearing from you!

Best regards,
Dipak Bundheliya
Bacancy Technology
dipak.bundheliya@bacancy.com
"""

        try:
            message = EmailMessage()
            message.set_content(body)
            message["To"] = recipient_email
            message["From"] = "dipak.bundheliya@bacancy.com"
            message["Subject"] = subject

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {"raw": encoded_message}
            
            send_message = (
                self.service.users()
                .messages()
                .send(userId="me", body=create_message)
                .execute()
            )
            
            message_id = send_message["id"]
            print(f'Service offering email sent! Message Id: {message_id}')
            
            # Track this conversation
            conversations = self.load_conversation_data()
            conversations[recipient_email] = {
                'initial_message_id': message_id,
                'recipient_name': recipient_name,
                'cycle_count': 1,
                'last_sent_time': datetime.now().isoformat(),
                'status': 'waiting_for_reply',
                'conversation_history': [
                    {
                        'type': 'sent',
                        'message_id': message_id,
                        'subject': subject,
                        'body': body,
                        'timestamp': datetime.now().isoformat()
                    }
                ]
            }
            self.save_conversation_data(conversations)
            
            return message_id
            
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None

    def get_email_content(self, message_id):
        """Get the content of a specific email"""
        try:
            message = self.service.users().messages().get(userId='me', id=message_id, format='full').execute()
            
            headers = message['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
            
            # Extract body
            body = ""
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        data = part['body']['data']
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
            else:
                if message['payload']['mimeType'] == 'text/plain':
                    data = message['payload']['body']['data']
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
            
            return {
                'id': message_id,
                'subject': subject,
                'sender': sender,
                'date': date,
                'body': body
            }
        except HttpError as error:
            print(f'An error occurred: {error}')
            return None

    def analyze_reply_sentiment(self, email_body):
        """Analyze the sentiment and intent of the reply"""
        email_lower = email_body.lower()
        
        # Positive indicators
        positive_words = ['interested', 'yes', 'sounds good', 'tell me more', 'discuss', 'meeting', 'call', 'schedule']
        negative_words = ['not interested', 'no thanks', 'remove', 'unsubscribe', 'stop', 'spam']
        question_words = ['how', 'what', 'when', 'where', 'pricing', 'cost', 'timeline']
        
        positive_score = sum(1 for word in positive_words if word in email_lower)
        negative_score = sum(1 for word in negative_words if word in email_lower)
        question_score = sum(1 for word in question_words if word in email_lower)
        
        if negative_score > 0:
            return 'negative'
        elif positive_score > 0:
            return 'positive'
        elif question_score > 0:
            return 'questions'
        else:
            return 'neutral'

    def generate_response(self, recipient_email, reply_content, sentiment, cycle_count):
        """Generate appropriate response based on sentiment and cycle count"""
        
        conversations = self.load_conversation_data()
        recipient_name = conversations.get(recipient_email, {}).get('recipient_name', '')
        
        if sentiment == 'positive':
            if cycle_count == 2:
                subject = "Re: Transform Your Business with Custom Software Solutions"
                body = f"""Hi {recipient_name},

Thank you for your positive response! I'm excited about the possibility of working together.

To better understand your needs, could you please share:

1. What type of project are you considering?
2. What's your expected timeline?
3. Do you have a preferred budget range?

I'd be happy to schedule a brief call to discuss your requirements in detail. I'm available this week for a 15-20 minute conversation.

Best regards,
Dipak Bundheliya"""

            elif cycle_count == 3:
                subject = "Re: Transform Your Business with Custom Software Solutions"
                body = f"""Hi {recipient_name},

Thanks for the additional information! Based on our conversation, I believe we can definitely help you achieve your goals.

I'd like to propose a quick discovery call where we can:
• Understand your exact requirements
• Share relevant case studies
• Provide a preliminary project estimate
• Discuss our development process

Would you prefer a call this week or next? I'm flexible with timing.

Looking forward to moving forward!

Best regards,
Dipak Bundheliya"""

            else:
                subject = "Re: Transform Your Business with Custom Software Solutions"
                body = f"""Hi {recipient_name},

Perfect! Let's finalize the next steps.

I'll prepare a detailed proposal based on our discussions. Would you like me to:
1. Send a formal proposal document?
2. Schedule a technical discussion with our team?
3. Arrange a demo of similar projects we've built?

I'm committed to making this process as smooth as possible for you.

Best regards,
Dipak Bundheliya"""

        elif sentiment == 'questions':
            subject = "Re: Transform Your Business with Custom Software Solutions"
            body = f"""Hi {recipient_name},

Great questions! Let me address them:

Regarding pricing: Our projects typically range from $10K-$100K+ depending on complexity. We always provide detailed estimates after understanding requirements.

Timeline: Most projects take 3-6 months, but we can work with urgent timelines too.

Our process: Discovery → Design → Development → Testing → Deployment → Support

I'd be happy to discuss your specific situation in detail. Would a brief call work for you this week?

Best regards,
Dipak Bundheliya"""

        elif sentiment == 'neutral':
            if cycle_count == 2:
                subject = "Re: Transform Your Business with Custom Software Solutions"
                body = f"""Hi {recipient_name},

I wanted to follow up on my previous email about our software development services.

Perhaps I can share a specific example: We recently helped a company similar to yours increase their efficiency by 40% through custom automation.

Would you be interested in a brief case study that might be relevant to your industry?

No pressure - just want to make sure you have all the information you need.

Best regards,
Dipak Bundheliya"""

            else:
                subject = "Re: Transform Your Business with Custom Software Solutions"
                body = f"""Hi {recipient_name},

I understand you might be busy or still evaluating options.

If our services aren't a fit right now, no worries at all. However, if you'd like to keep in touch for future opportunities, I'm happy to stay connected.

Feel free to reach out anytime you need software development assistance.

Best regards,
Dipak Bundheliya"""

        else:  # negative
            subject = "Re: Transform Your Business with Custom Software Solutions"
            body = f"""Hi {recipient_name},

I completely understand that our services might not be the right fit at this time.

Thank you for taking the time to respond. I'll remove you from our outreach list.

If your needs change in the future, please feel free to reach out.

Best regards,
Dipak Bundheliya"""

        return subject, body

    def send_reply(self, recipient_email, subject, body):
        """Send a reply email"""
        try:
            message = EmailMessage()
            message.set_content(body)
            message["To"] = recipient_email
            message["From"] = "dipak.bundheliya@bacancy.com"
            message["Subject"] = subject

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {"raw": encoded_message}
            
            send_message = (
                self.service.users()
                .messages()
                .send(userId="me", body=create_message)
                .execute()
            )
            
            print(f'Reply sent! Message Id: {send_message["id"]}')
            return send_message["id"]
            
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None

    def check_for_replies(self):
        """Check for new replies to our outreach emails"""
        if not self.service:
            self.authenticate_gmail()
        
        conversations = self.load_conversation_data()
        
        # Get recent emails
        try:
            results = self.service.users().messages().list(userId='me', maxResults=20).execute()
            messages = results.get('messages', [])
            
            for message in messages:
                email_data = self.get_email_content(message['id'])
                if email_data:
                    sender_email = self.extract_email_from_sender(email_data['sender'])
                    
                    # Check if this is a reply to one of our conversations
                    if sender_email in conversations:
                        conv = conversations[sender_email]
                        
                        # Check if this is a new message (not in our history)
                        message_ids = [msg.get('message_id') for msg in conv['conversation_history']]
                        if email_data['id'] not in message_ids:
                            print(f"\n🔔 New reply from {sender_email}")
                            print(f"Subject: {email_data['subject']}")
                            print(f"Content: {email_data['body'][:200]}...")
                            
                            # Process this reply
                            self.process_reply(sender_email, email_data)
            
        except HttpError as error:
            print(f'An error occurred: {error}')

    def extract_email_from_sender(self, sender_string):
        """Extract email address from sender string"""
        if '<' in sender_string and '>' in sender_string:
            return sender_string.split('<')[1].split('>')[0]
        return sender_string

    def process_reply(self, sender_email, email_data):
        """Process a reply and send appropriate response"""
        conversations = self.load_conversation_data()
        conv = conversations[sender_email]
        
        # Check if we've reached max cycles
        if conv['cycle_count'] >= self.max_cycles:
            print(f"Max cycles reached for {sender_email}")
            return
        
        # Analyze sentiment
        sentiment = self.analyze_reply_sentiment(email_data['body'])
        print(f"Detected sentiment: {sentiment}")
        
        # Generate and send response
        subject, body = self.generate_response(sender_email, email_data['body'], sentiment, conv['cycle_count'] + 1)
        
        reply_message_id = self.send_reply(sender_email, subject, body)
        
        if reply_message_id:
            # Update conversation data
            conv['cycle_count'] += 1
            conv['last_sent_time'] = datetime.now().isoformat()
            conv['conversation_history'].extend([
                {
                    'type': 'received',
                    'message_id': email_data['id'],
                    'subject': email_data['subject'],
                    'body': email_data['body'],
                    'sentiment': sentiment,
                    'timestamp': datetime.now().isoformat()
                },
                {
                    'type': 'sent',
                    'message_id': reply_message_id,
                    'subject': subject,
                    'body': body,
                    'timestamp': datetime.now().isoformat()
                }
            ])
            
            # Stop conversation if negative sentiment
            if sentiment == 'negative':
                conv['status'] = 'ended_negative'
            elif conv['cycle_count'] >= self.max_cycles:
                conv['status'] = 'completed'
            else:
                conv['status'] = 'waiting_for_reply'
            
            conversations[sender_email] = conv
            self.save_conversation_data(conversations)

# Main functions to use
def start_conversation_with_prospect(email, name=""):
    """Start a new conversation with a prospect"""
    manager = ConversationManager()
    return manager.send_service_offering_email(email, name)

def check_and_respond_to_replies():
    """Check for replies and respond automatically"""
    manager = ConversationManager()
    manager.check_for_replies()

if __name__ == "__main__":
    # Example usage
    action = input("What would you like to do? (start/check): ").lower().strip()
    
    if action == "start":
        email = input("Enter prospect email: ").strip()
        name = input("Enter prospect name (optional): ").strip()
        start_conversation_with_prospect(email, name)
    elif action == "check":
        print("Checking for replies...")
        check_and_respond_to_replies()
    else:
        print("Invalid action. Choose 'start' or 'check'")
