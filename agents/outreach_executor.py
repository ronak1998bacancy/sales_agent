# outreach_executor.py
import smtplib
from email.mime.text import MIMEText
from typing import List, Dict
from dotenv import load_dotenv
import os
import datetime
import time
import logging  # Added logging
# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class OutreachExecutorAgent:
    name = "outreach_executor"
    description = "Executes outreach by sending emails with delays"
    input_schema = {"leads": List[Dict]}
    output_schema = {"leads": List[Dict]}  # Update same leads list

    async def run(self, state):
        print(f"[{datetime.datetime.now()}] Starting outreach_executor")  # Kept print for consistency
        leads = state.get("leads", [])  # Use .get to avoid KeyError
        for lead in leads:
            if "email_draft" in lead and "email_sent" not in lead:  # Skip if already sent
                to_email = lead.get("email", "lead@example.com")
                draft = lead.get("email_draft", {})
                # msg = MIMEText(draft.get("body", "") + "<br><br>" + draft.get("cta", ""), _subtype="html")
                html_content = f"""
                                <html>
                                <body>
                                    {draft.get("body", "")}<br>
                                    {draft.get("cta", "")}
                                </body>
                                </html>
                                """
                msg = MIMEText(html_content, _subtype="html")

                msg["Subject"] = draft.get("subject", "Default Subject")
                msg["From"] = os.getenv("SMTP_USER")
                msg["To"] = to_email
                try:
                    with smtplib.SMTP(os.getenv("SMTP_HOST"), 587) as server:
                        server.starttls()
                        server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
                        server.send_message(msg)
                    logger.info(f"Email sent to {to_email} for lead {lead.get('profile_url', 'unknown')}")
                    lead["email_sent"] = True
                    lead["email_sent_time"] = datetime.datetime.now().isoformat()
                    time.sleep(5)  # Delay for sequencing
                except Exception as e:
                    logger.error(f"Error sending email to {to_email}: {e}", exc_info=True)
        print(f"[{datetime.datetime.now()}] Completed outreach_executor: Emails sent for {len(leads)} leads")
        return {"leads": leads}