# email_writer.py
import json
from pydantic import BaseModel
from typing import List, Dict
from openai import OpenAI
from dotenv import load_dotenv
import os
import datetime

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
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def run(self, state):
        print(f"[{datetime.datetime.now()}] Starting email_writer")
        leads = state["leads"]
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
            Write a professional, Indian-toned outreach email for lead: Name - {lead.get('name', 'Unknown')}, Role - {lead.get('role', 'Unknown')}, Company - {lead.get('company', 'Unknown')}, Location - {lead.get('location', 'Unknown')}
            Context: Experience - {lead.get('experience', '')}, Company Domain - {lead.get('company_website', '')}
            Personalize based on their experience and company domain, offering our AI services.
            Create a 3-step sequence. Avoid outsourcing clichés.
            Include signature: {signature}
            
            Output strictly in the following format:
            Subject: [Your subject here]
            
            Body: [Your email body here, including the 3-step sequence]
            
            CTA: [Your call to action here]
            """
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            email_content = response.choices[0].message.content
            try:
                subject = email_content.split("Subject:")[1].split("Body:")[0].strip()
                body = email_content.split("Body:")[1].split("CTA:")[0].strip()
                cta = email_content.split("CTA:")[1].strip()
            except IndexError:
                lines = email_content.split("\n")
                subject = lines[0].strip() if lines else "Default Subject"
                body = "\n".join(lines[1:-1]).strip() if len(lines) > 1 else "Default Body"
                cta = lines[-1].strip() if len(lines) > 1 else "Default CTA"
            
            lead["email_draft"] = {
                "subject": subject,
                "body": body,
                "cta": cta
            }
            with open(f"outputs/emails/{lead.get('profile_url', 'unknown').replace('/', '_')}.json", "w") as f:
                json.dump(lead["email_draft"], f, indent=2)
        print(f"[{datetime.datetime.now()}] Completed email_writer: Emails generated for {len(leads)} leads")
        return {"leads": leads}