# email_reviewer.py
from typing import List, Dict
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import os
import datetime
import logging
import base64
import json
import smtplib
from email.mime.text import MIMEText
from openai import OpenAI
# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class DeepSeekClient:
    """
    Client for DeepSeek API, compatible with OpenAI format.
    """
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com/")

    def chat_completions_create(self, model, messages):
        return self.client.chat.completions.create(
            model=model,
            messages=messages
        )

deepseek_client = DeepSeekClient()

class EmailReviewerAgent:
    """
    Agent to review Gmail for replies to sent emails.
    - Checks for replies based on subject and sender.
    - Classifies replied/non-replied, stores in separate JSON folders.
    - Analyzes reply content for intent/interest.
    - Sends follow-up based on classification.
    """
    name = "email_reviewer"
    description = "Reviews and parses emails for replies and stages"
    input_schema = {"leads": List[Dict]}
    output_schema = {"leads": List[Dict]}

    def __init__(self):
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/calendar'
        ]
        self.credentials_path = os.getenv("GOOGLE_OAUTH_CREDENTIALS_PATH")
        self.token_path = 'token.json'
        self.service = self.get_gmail_service()

    def get_gmail_service(self):
        """
        Initializes Gmail service with proper scopes, re-authenticates if necessary.
        """
        try:
            creds = None
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
            if not creds or not creds.valid or set(creds.scopes) != set(self.scopes):
                logger.warning("Token invalid or scopes mismatch. Re-authenticating.")
                if os.path.exists(self.token_path):
                    os.remove(self.token_path)  # Remove invalid token
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"Credentials file not found at {self.credentials_path}")
                with open(self.credentials_path, 'r') as f:
                    creds_info = json.load(f)
                    if 'installed' not in creds_info:
                        raise ValueError("Invalid credentials format")
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.scopes)
                creds = flow.run_local_server(port=0)
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            else:
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
            service = build('gmail', 'v1', credentials=creds)
            service.users().getProfile(userId="me").execute()
            logger.info("Gmail API initialized with full scopes.")
            return service
        except Exception as e:
            logger.error(f"Failed to initialize Gmail service: {str(e)}")
            return None

    async def run(self, state):
        """
        Runs email review process.
        - For each lead with sent email, queries Gmail for matching replies (same subject, from lead email).
        - If replied: analyzes content, classifies interest, stores in replied JSON, sends follow-up.
        - If not replied: stores in non-replied JSON.
        - Handles KeyError/TypeError by safe dict access.
        """
        logger.info(f"[{datetime.datetime.now()}] Starting email_reviewer")
        if self.service is None:
            logger.warning("Gmail service not available.")
            return {"leads": state.get("leads", [])}

        leads = state.get("leads", [])
        lead_emails = {lead.get("email", "") for lead in leads if lead.get("email", "")}

        try:
            for lead in leads:
                email_draft = lead.get("email_draft", {})
                subject = email_draft.get("subject", "")
                sent_time_str = lead.get("email_sent_time", "")
                lead_email = lead.get("email", "")

                if not lead.get("email_sent", False) or not lead_email or lead_email not in lead_emails:
                    continue

                # Query for replies: same subject, from lead_email, after sent_time
                sent_time = datetime.datetime.fromisoformat(sent_time_str) if sent_time_str else datetime.datetime.min
                query = f"from:{lead_email} subject:\"{subject}\" after:{int(sent_time.timestamp())}"
                results = self.service.users().messages().list(userId="me", q=query).execute()
                messages = results.get("messages", [])

                if messages:
                    # Process first matching reply (assume latest)
                    msg = messages[0]
                    msg_data = self.service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
                    payload = msg_data.get("payload", {})
                    body_data = ""
                    if "parts" in payload:
                        for part in payload.get("parts", []):
                            if part.get("mimeType") == "text/plain":
                                body_data = base64.urlsafe_b64decode(part["body"].get("data", "")).decode("utf-8")
                                break
                    elif "body" in payload and "data" in payload["body"]:
                        body_data = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")

                    # Analyze with DeepSeek
                    prompt = f"""
                    Analyze reply: {body_data}
                    Classify interest:
                    - 'interested' if positive or requests more info/meeting/proposal.
                    - 'not_interested' if rejection.
                    - 'other' if unclear.
                    If 'interested', check for meeting request and parse time/date if mentioned (YYYY-MM-DD HH:MM, timezone or UTC).
                    Output JSON: {{"summary": "brief summary", "interest": "interested/not_interested/other", "preferred_meeting_time": "YYYY-MM-DD HH:MM" or null, "timezone": "UTC" or specified}}
                    """
                    response = deepseek_client.chat_completions_create("deepseek-chat", [{"role": "user", "content": prompt}])
                    interest_json = json.loads(response.choices[0].message.content) if response else {"interest": "other", "summary": "Error"}

                    lead["email_review"] = {
                        "status": "replied",
                        "full_body": body_data,
                        "analysis": interest_json
                    }

                    # Store replied JSON
                    replied_data = {
                        "name": lead.get("name", "Unknown"),
                        "company": lead.get("company", "Unknown"),
                        "linkedin_url": lead.get("profile_url", "Unknown"),
                        "reply_body": body_data,
                        "analysis": interest_json
                    }
                    replied_path = f"outputs/replied/{lead.get('profile_url', 'unknown').replace('/', '_')}.json"
                    with open(replied_path, "w") as f:
                        json.dump(replied_data, f, indent=2)

                    # Send follow-up based on interest
                    if interest_json.get("interest") == "interested":
                        follow_up_body = "Thank you for your interest. Let's proceed."
                    elif interest_json.get("interest") == "not_interested":
                        follow_up_body = "Noted, thank you."
                    else:
                        follow_up_body = "Clarifying your response."
                    to_email = lead_email
                    msg = MIMEText(follow_up_body)
                    msg["Subject"] = f"Re: {subject}"
                    msg["From"] = os.getenv("SMTP_USER")
                    msg["To"] = to_email
                    with smtplib.SMTP(os.getenv("SMTP_HOST"), 587) as server:
                        server.starttls()
                        server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
                        server.send_message(msg)
                    logger.info(f"Sent follow-up to {to_email}")

                    # Mark as read
                    self.service.users().messages().modify(userId="me", id=msg["id"], body={"removeLabelIds": ["UNREAD"]}).execute()
                else:
                    # Non-replied
                    lead["email_review"] = {"status": "pending"}
                    non_replied_data = {
                        "name": lead.get("name", "Unknown"),
                        "company": lead.get("company", "Unknown"),
                        "company_url": lead.get("company_url", "Unknown"),
                        "profile_url": lead.get("profile_url", "Unknown")
                    }
                    non_replied_path = f"outputs/non_replied/{lead.get('profile_url', 'unknown').replace('/', '_')}.json"
                    with open(non_replied_path, "w") as f:
                        json.dump(non_replied_data, f, indent=2)

        except HttpError as e:
            logger.error(f"Gmail error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")

        logger.info(f"[{datetime.datetime.now()}] Completed email_reviewer")
        return {"leads": leads}