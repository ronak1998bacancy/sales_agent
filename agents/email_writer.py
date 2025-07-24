# email_writer.py
import json
from pydantic import BaseModel
from typing import List, Dict
from openai import OpenAI
from dotenv import load_dotenv
import os
import datetime
from google import genai
import re  # Added for regex parsing
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class Email(BaseModel):
    subject: str
    body: str
    cta: str
    lead_id: str

class EmailWriterAgent:
    name = "email_writer"
    description = "Generates personalized outreach emails"
    input_schema = {"leads": List[Dict]}
    output_schema = {"leads": List[Dict]}  # Update same leads list

    def __init__(self):
        # self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    async def run(self, state):
        print(f"[{datetime.datetime.now()}] Starting email_writer")
        leads = state.get("leads", [])
        org_name = state.get("organization_name", "Your Company")
        user_name = state.get("user_name", "Sales Team")
        company_email = state.get("company_email", "sales@company.com")
        company_website = state.get("company_website", "https://yourcompany.com")
        company_linkedin = state.get("company_linkedin", "https://linkedin.com/company/yourcompany")
        company_logo = state.get("company_logo", "https://yourcompany.com/logo.png")  # URL or base64
        
        for lead in leads:
            if "email_draft" in lead:  # Skip if already drafted
                continue
            signature = f"""
                            Best regards,<br>
                            {user_name}<br>
                            {org_name}<br>
                            Email: <a href="mailto:{company_email}">{company_email}</a><br>
                            <a href="https://www.bacancytechnology.com">
                            <img src="https://assets.bacancytechnology.com/main-boot-5/images/bacancy-logo-white.svg" 
                                alt="Company Logo" width="100" style="vertical-align:middle;">
                            </a><br>
                            <a href="https://www.linkedin.com/company/bacancy-technology">
                            <img src="https://static-exp1.licdn.com/sc/h/al2o9zrvru7aqj8e1x2rzsrca" 
                                alt="LinkedIn" width="20" style="vertical-align:middle;">
                            </a>
                            """
            prompt = f"""
            Write a professional, Indian-toned outreach email for the lead:
            Name - {lead.get('name', 'Unknown')}, 
            Role - {lead.get('role', 'Unknown')}, 
            Company - {lead.get('company', 'Unknown')}, 
            Location - {lead.get('location', 'Unknown')}.

            Context:
            Experience - {lead.get('experience', '')}, 
            Company Domain - {lead.get('company_website', '')}

            Personalize the email based on their experience and company domain, offering our AI services.

            ✅ Format the email as ONE email with a 3-step value proposition clearly explained within the **body** (do not write 3 separate emails). Avoid outsourcing clichés.

            Use a professional yet conversational tone.

            Include this email signature at the end:
            {signature}

            Output strictly in the following format:

            Subject: [Your subject here]

            Body: [Your email body here, including the 3-step value proposition]

            CTA: [Your call to action here]
            """
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash", contents=prompt
                )
                email_content = response.text
            except Exception as e:
                logger.error(f"Error generating email with AI: {e}", exc_info=True)
                email_content = ""

            # Improved parsing with regex to handle variations
            subject_match = re.search(r'Subject:\s*(.*?)(\n\nBody:|$)', email_content, re.DOTALL)
            body_match = re.search(r'Body:\s*(.*?)(\n\nCTA:|$)', email_content, re.DOTALL)
            cta_match = re.search(r'CTA:\s*(.*)', email_content, re.DOTALL)
            
            subject = subject_match.group(1).strip() if subject_match else "Default Subject"
            body = body_match.group(1).strip() if body_match else "Default Body"
            cta = cta_match.group(1).strip() if cta_match else "Default CTA"
            
            lead["email_draft"] = {
                "subject": subject,
                "body": body,
                "cta": cta
            }
            try:
                with open(f"outputs/emails/{lead.get('profile_url', 'unknown').replace('/', '_')}.json", "w") as f:
                    json.dump(lead["email_draft"], f, indent=2)
            except Exception as e:
                logger.error(f"Error saving email draft: {e}", exc_info=True)
        print(f"[{datetime.datetime.now()}] Completed email_writer: Emails generated for {len(leads)} leads")
        return {"leads": leads}