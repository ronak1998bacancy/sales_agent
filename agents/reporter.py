# reporter.py
import smtplib
from email.mime.text import MIMEText
from typing import Dict, List
from dotenv import load_dotenv
import os
import datetime
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class ReporterAgent:
    name = "reporter"
    description = "Generates daily activity summary"
    input_schema = {"leads": List[Dict]}
    output_schema = {"summary": str}

    async def run(self, state):
        print(f"[{datetime.datetime.now()}] Starting reporter")
        organization_name = state.get("organization_name", "Your Organization")
        user_name = state.get("user_name", "Sales Team")
        leads = state.get("leads", [])
        summary = f"""
        Daily Sales Report for {organization_name}:
        - Leads Discovered: {len(leads)}
        - Emails Sent: {sum(1 for l in leads if 'email_sent' in l)}
        - Proposals Generated: {sum(1 for l in leads if 'proposal' in l)}
        """
        msg = MIMEText(summary)
        msg["Subject"] = f"Daily Sales Pipeline Report - {organization_name}"
        msg["From"] = f"{user_name} <sales@{organization_name.lower().replace(' ', '')}.com>"
        msg["To"] = "team@example.com"
        
        try:
            with smtplib.SMTP(os.getenv("SMTP_HOST"), 587) as server:
                server.starttls()
                server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
                server.send_message(msg)
            logger.info("Summary email sent successfully")
        except Exception as e:
            logger.error(f"Error sending summary email: {e}", exc_info=True)
        
        # Central JSON already dumped in main.py, but log here
        print(f"[{datetime.datetime.now()}] Completed reporter: Summary sent")
        return {"summary": summary}