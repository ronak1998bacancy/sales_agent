# outreach_executor.py
import smtplib
from email.mime.text import MIMEText
from typing import List, Dict
from dotenv import load_dotenv
import os
import datetime
import time

# Load environment variables
load_dotenv()

class OutreachExecutorAgent:
    name = "outreach_executor"
    description = "Executes outreach by sending emails with delays"
    input_schema = {"leads": List[Dict]}
    output_schema = {"leads": List[Dict]}  # Update same leads list

    async def run(self, state):
        print(f"[{datetime.datetime.now()}] Starting outreach_executor")
        leads = state["leads"]
        for lead in leads:
            if "email_draft" in lead and "email_sent" not in lead:  # Skip if already sent
                to_email = lead.get("email", "lead@example.com")
                draft = lead["email_draft"]
                msg = MIMEText(draft["body"] + "\n\n" + draft["cta"])
                msg["Subject"] = draft["subject"]
                msg["From"] = os.getenv("SMTP_USER")
                msg["To"] = to_email
                with smtplib.SMTP(os.getenv("SMTP_HOST"), 587) as server:
                    server.starttls()
                    server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
                    server.send_message(msg)
                print(f"Email sent to {to_email} for lead {lead.get('profile_url', 'unknown')}")
                lead["email_sent"] = True
                lead["email_sent_time"] = datetime.datetime.now().isoformat()
                time.sleep(5)  # Delay for sequencing
        print(f"[{datetime.datetime.now()}] Completed outreach_executor: Emails sent for {len(leads)} leads")
        return {"leads": leads}