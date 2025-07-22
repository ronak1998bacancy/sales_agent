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
from datetime import timedelta  # Added for time check
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

    def chat_completions_create(self, model, messages, response_format=None):
        params = {
            "model": model,
            "messages": messages
        }
        if response_format:
            params["response_format"] = response_format
        return self.client.chat.completions.create(**params)

deepseek_client = DeepSeekClient()

class EmailReviewerAgent:
    """
    Agent to review Gmail for replies to sent emails.
    - Checks for replies based on subject and sender.
    - Classifies replied/non-replied, stores in separate JSON folders.
    - Analyzes reply content for intent/interest.
    - Sends follow-up based on classification.
    - Merged: Handles time-based follow-up nudges for non-replied leads.
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
            logger.error(f"Failed to initialize Gmail service: {str(e)}", exc_info=True)
            return None

    def save_leads_state(self, leads):
        """
        Saves the updated leads state to final_leads.json immediately.
        """
        leads_file = "outputs/final_leads.json"
        try:
            with open(leads_file, "w") as f:
                json.dump(leads, f, indent=2)
            logger.info(f"Updated leads saved to {leads_file} after processing")
        except Exception as e:
            logger.error(f"Error saving leads: {e}", exc_info=True)

    async def run(self, state):
        logger.info(f"[{datetime.datetime.now()}] Starting email_reviewer")
        if self.service is None:
            logger.warning("Gmail service not available.")
            return {"leads": state.get("leads", [])}

        leads = state.get("leads", [])
        lead_emails = {lead.get("email", "") for lead in leads if lead.get("role", "")}

        try:
            for i, lead in enumerate(leads):
                review = lead.get("email_review", {})
                if review.get("status") == "replied":
                    logger.info(f"Skipping already replied lead: {lead.get('profile_url', 'unknown')}")
                    continue  # Skip if already replied

                email_draft = lead.get("email_draft", {})
                subject = email_draft.get("subject", "")
                if not subject:
                    continue  # Skip if no subject
                sent_time_str = lead.get("email_sent_time", "")
                lead_email = lead.get("email", "")

                if not lead.get("email_sent", False) or not lead_email or lead_email not in lead_emails:
                    continue

                # Query for replies: subject matches original or Re:, from lead_email, after sent_time
                sent_time = datetime.datetime.fromisoformat(sent_time_str) if sent_time_str else datetime.datetime.min
                query = f"from:{lead_email} subject:(\"{subject}\" OR \"Re: {subject}\") after:{int(sent_time.timestamp())}"
                try:
                    results = self.service.users().messages().list(userId="me", q=query).execute()
                    messages = results.get("messages", [])
                except HttpError as e:
                    logger.error(f"Gmail query error: {e}", exc_info=True)
                    messages = []

                if messages:
                    # Process first matching reply (assume latest)
                    msg_id = messages[0]["id"]
                    try:
                        msg_data = self.service.users().messages().get(userId="me", id=msg_id, format="full").execute()
                        payload = msg_data.get("payload", {})
                        body_data = ""
                        if "parts" in payload:
                            for part in payload.get("parts", []):
                                if part.get("mimeType") == "text/plain" and "body" in part and "data" in part["body"]:
                                    body_data = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                                    break
                        elif "body" in payload and "data" in payload["body"]:
                            body_data = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
                    except HttpError as e:
                        logger.error(f"Error getting message {msg_id}: {e}", exc_info=True)
                        body_data = ""

                    if not body_data:
                        logger.warning(f"No body data for message {msg_id}")
                        continue

                    # Analyze with DeepSeek, force JSON
                    prompt = """
    You must respond with valid JSON only. No additional text, no explanations, no markdown. The response must be a single JSON object starting with { and ending with }.
    Analyze the reply: {body_data}
    Classify interest:
    - 'interested' if positive or requests more info/meeting/proposal.
    - 'not_interested' if rejection.
    - 'other' if unclear.
    If 'interested', check for meeting request and parse time/date if mentioned. Output start and end in Google Calendar format: {{"dateTime": "YYYY-MM-DDTHH:MM:SS", "timeZone": "timezone or UTC"}}. Assume 30 min duration if not specified. Use current date July 22, 2025 for relative dates.
    JSON structure: {{"summary": "brief summary", "interest": "interested/not_interested/other", "meeting_details": {{"start": {{"dateTime": "YYYY-MM-DDTHH:MM:SS", "timeZone": "timezone"}}, "end": {{"dateTime": "YYYY-MM-DDTHH:MM:SS", "timeZone": "timezone"}}}} or null if no meeting}}
    Ensure all keys are present and values are correct types. If parse fails, use defaults like null for meeting_details.
    """.replace("{body_data}", body_data)
                    try:
                        response = deepseek_client.chat_completions_create(
                            "deepseek-chat", 
                            [{"role": "user", "content": prompt}],
                            response_format={"type": "json_object"}
                        )
                        raw_content = response.choices[0].message.content if response and response.choices else "{}"
                        logger.info(f"Raw LLM response: {raw_content}")
                    except Exception as e:
                        logger.error(f"Error analyzing with DeepSeek: {e}", exc_info=True)
                        raw_content = "{}"

                    try:
                        interest_json = json.loads(raw_content)
                        # Ensure all keys exist to avoid KeyError
                        required_keys = ["summary", "interest", "meeting_details"]
                        for key in required_keys:
                            if key not in interest_json:
                                interest_json[key] = None if key == "meeting_details" else "other" if key == "interest" else "Parse error"
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON parse error: {str(e)}. Raw: {raw_content}", exc_info=True)
                        interest_json = {"summary": "Parse error", "interest": "other", "meeting_details": None}

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
                    try:
                        with open(replied_path, "w") as f:
                            json.dump(replied_data, f, indent=2)
                        logger.info(f"Saved replied JSON at {replied_path}")
                    except Exception as e:
                        logger.error(f"Error saving replied JSON: {e}", exc_info=True)

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
                    try:
                        with smtplib.SMTP(os.getenv("SMTP_HOST"), 587) as server:
                            server.starttls()
                            server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
                            server.send_message(msg)
                        logger.info(f"Sent follow-up to {to_email}")
                    except Exception as e:
                        logger.error(f"Error sending follow-up: {e}", exc_info=True)

                    # Mark as read
                    try:
                        self.service.users().messages().modify(userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}).execute()
                    except HttpError as e:
                        logger.error(f"Error marking email as read: {e}", exc_info=True)
                else:
                    # Non-replied (pending)
                    lead["email_review"] = {"status": "pending"}
                    non_replied_data = {
                        "name": lead.get("name", "Unknown"),
                        "company": lead.get("company", "Unknown"),
                        "company_url": lead.get("company_url", "Unknown"),
                        "profile_url": lead.get("profile_url", "Unknown")
                    }
                    non_replied_path = f"outputs/non_replied/{lead.get('profile_url', 'unknown').replace('/', '_')}.json"
                    try:
                        with open(non_replied_path, "w") as f:
                            json.dump(non_replied_data, f, indent=2)
                        logger.info(f"Saved non-replied JSON at {non_replied_path}")
                    except Exception as e:
                        logger.error(f"Error saving non-replied JSON: {e}", exc_info=True)

                    # Merged follow-up logic: Check time and send nudge if exceeded
                    if lead.get("email_sent", False) and (datetime.datetime.now() - sent_time) >= timedelta(days=1) and "follow_up_sent" not in lead:
                        prompt = f"Generate polite nudge email for lead {lead.get('profile_url', 'unknown')} - no reply yet."
                        try:
                            response = deepseek_client.chat_completions_create("deepseek-chat", [{"role": "user", "content": prompt}])
                            follow_up_text = response.choices[0].message.content if response and response.choices else "Follow-up message."
                        except Exception as e:
                            logger.error(f"Error generating nudge with DeepSeek: {e}", exc_info=True)
                            follow_up_text = "Follow-up message."

                        to_email = lead.get("email", "")
                        subject = lead.get("email_draft", {}).get("subject", "Follow-up")
                        msg = MIMEText(follow_up_text)
                        msg["Subject"] = f"Re: {subject}"
                        msg["From"] = os.getenv("SMTP_USER")
                        msg["To"] = to_email
                        try:
                            with smtplib.SMTP(os.getenv("SMTP_HOST"), 587) as server:
                                server.starttls()
                                server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
                                server.send_message(msg)
                            lead["follow_up_sent"] = True
                            logger.info(f"Follow-up sent to {to_email}")
                        except Exception as e:
                            logger.error(f"Error sending nudge: {e}", exc_info=True)

                # Save main leads JSON after each lead
                self.save_leads_state(leads)

        except HttpError as e:
            logger.error(f"Gmail error: {str(e)}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)

        logger.info(f"[{datetime.datetime.now()}] Completed email_reviewer")
        return {"leads": leads}