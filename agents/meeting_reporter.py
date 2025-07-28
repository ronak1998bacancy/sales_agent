import os
import json
import smtplib
import datetime
import logging
from email.mime.text import MIMEText

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MeetingReporter:
    async def run(self, state):
        print(f"[{datetime.datetime.now()}] Starting meeting_reporter")
        leads = state.get("leads", [])
        if not leads:
            logger.info("No leads available for meeting reporting")
            return state

        sections = []

        for lead in leads:
            if lead.get("send_meeting_info"):
                continue

            lead_id = lead.get("lead_id", "unknown")
            email_review = lead.get("email_review", {})
            if not email_review:
                logger.warning(f"No email review found for lead {lead_id}")
                continue
            
            interest_json = email_review.get("analysis", {}).get("intersted", {})
            if interest_json == "not_interested":
                logger.warning(f"No interest analysis found for lead {lead_id}")
                continue
            
            # Generate report content
            if email_review.get('analysis', {}).get('meeting_details', {}):
                True
                sections.append(f"""
                - Lead Name: {lead.get('name', 'Unknown')}
                - Lead profile: {lead.get('profile_url', 'Unknown')}
                - Arranged meeting start time: {email_review.get('analysis', {}).get('meeting_details', {}).get('start', {}).get('dateTime', 'unknown')}
                - Arranged meeting end time: {email_review.get('analysis', {}).get('meeting_details', {}).get('end', {}).get('dateTime', 'unknown')}
                - Meeting link: {lead.get('meeting', {}).get('hangoutLink', 'unknown')}
                """)

                lead["send_meeting_info"] = True

        report_content = "Here is the details of persons which are intersted in our services\n" + "\n".join(sections)
        True
        if sections:
            organization_name = state.get("organization_name", "Your Organization")
            user_name = state.get("user_name", "Sales Team")

            msg = MIMEText(report_content)
            msg["Subject"] = f"Lead Response Meeting Report - {organization_name}"
            msg["From"] = f"{user_name} <sales@{organization_name.lower().replace(' ', '')}.com>"
            msg["To"] = os.getenv("REPORT_EMAIL_ID")

            try:
                with smtplib.SMTP(os.getenv("SMTP_HOST"), 587) as server:
                    server.starttls()
                    server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
                    server.send_message(msg)
                logger.info("Meeting details sent successfully")
            except Exception as e:
                logger.error(f"Error sending meeting details: {e}", exc_info=True) 
 

        # Generate a report for each lead
        print(f"[{datetime.datetime.now()}] Completed meeting_reporter task")

        with open("outputs/final_leads.json", "w") as f:
            json.dump(leads, f, indent=2)
        True
        return state