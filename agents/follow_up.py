# follow_up.py
from typing import List, Dict
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
import datetime
from datetime import timedelta
from openai import OpenAI
# Load environment variables
load_dotenv()

class FollowUpAgent:
    """
    Agent to send follow-up nudges for non-replied leads after time threshold.
    """
    name = "follow_up"
    description = "Handles follow-ups for non-replied leads"
    input_schema = {"leads": List[Dict]}
    output_schema = {"leads": List[Dict]}

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com/")

    async def run(self, state):
        """
        Checks non-replied leads and sends nudge if time exceeded.
        """
        print(f"[{datetime.datetime.now()}] Starting follow_up")
        leads = state.get("leads", [])
        for lead in leads:
            review = lead.get("email_review", {})
            if lead.get("email_sent", False) and review.get("status") == "pending" and "follow_up_sent" not in lead:
                sent_time_str = lead.get("email_sent_time", "")
                if sent_time_str:
                    sent_time = datetime.datetime.fromisoformat(sent_time_str)
                    if (datetime.datetime.now() - sent_time) >= timedelta(days=1):  # Define time between (1 day)
                        prompt = f"Generate polite nudge email for lead {lead.get('profile_url', 'unknown')} - no reply yet."
                        response = self.client.chat_completions_create("deepseek-chat", [{"role": "user", "content": prompt}])
                        follow_up_text = response.choices[0].message.content if response else "Follow-up message."

                        to_email = lead.get("email", "")
                        subject = lead.get("email_draft", {}).get("subject", "Follow-up")
                        msg = MIMEText(follow_up_text)
                        msg["Subject"] = f"Re: {subject}"
                        msg["From"] = os.getenv("SMTP_USER")
                        msg["To"] = to_email
                        with smtplib.SMTP(os.getenv("SMTP_HOST"), 587) as server:
                            server.starttls()
                            server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
                            server.send_message(msg)
                        lead["follow_up_sent"] = True
                        print(f"Follow-up sent to {to_email}")
        print(f"[{datetime.datetime.now()}] Completed follow_up")
        return {"leads": leads}