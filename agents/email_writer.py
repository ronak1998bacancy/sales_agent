# email_writer.py
import json
from pydantic import BaseModel
from typing import List, Dict
from dotenv import load_dotenv
import os
import datetime
import logging
from google import genai
# from google.generativeai.types import GenerationConfig
from google.genai import types

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure Gemini
# genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

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
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    async def run(self, state):
        print(f"[{datetime.datetime.now()}] Starting email_writer")
        leads = state.get("leads", [])
        org_name = state.get("organization_name", "Your Company")
        user_name = state.get("user_name", "Sales Team")
        company_email = state.get("company_email", "sales@company.com")
        company_website = state.get("company_website", "https://yourcompany.com")
        company_linkedin = state.get("company_linkedin", "https://linkedin.com/company/yourcompany")
        company_logo = state.get("company_logo", "https://assets.bacancytechnology.com/main-boot-5/images/bacancy-logo-white.svg")  # Use base64 from state if available
        logo_src = company_logo
        if logo_src.startswith('http'):  # URL: use as-is (may not load)
            pass
        elif logo_src.startswith('data:'):  # Base64: embedded, will load
            pass
        else:
            logo_src = "https://assets.bacancytechnology.com/main-boot-5/images/bacancy-logo-white.svg"

        linkedin_icon_src = "https://img.icons8.com/?size=100&id=xuvGCOXi8Wyg&format=png&color=000000png"  # LinkedIn icon URL
        
        signature = f"""
                        <br><br>
                        Best regards,<br>
                        <b>{user_name}</b><br>
                        {org_name}<br>
                        Email: <a href="mailto:{company_email}">{company_email}</a><br>
                        <a href="{company_website}" style="text-decoration:none;">
                            <img src="{logo_src}" 
                                alt="{org_name}" width="120" style="margin-top:8px;">
                        </a>&nbsp;
                        <a href="{company_linkedin}" style="text-decoration:none;">
                            <img src="{linkedin_icon_src}" 
                                alt="LinkedIn" width="20" style="vertical-align:middle;">
                        </a>
                        """
        for lead in leads:
            if "email_draft" in lead:
                continue

            # Updated prompt for JSON output
            prompt = f"""
            IMPORTANT: Output ONLY a JSON object with keys 'subject' and 'body'. NO other text, NO explanations, NO extras. The 'body' should be HTML-ready, include the CTA as the last paragraph, and be detailed but concise (150-200 words), professional, humanized—like a tech professional from India.

            Example Output:
            {{
                "subject": "Exploring AI for Acme Corp's Apps",
                "body": "Hi Jane,<br>I hope you're doing well.<br>I'm John Doe from Bacancy Technology. I came across the exciting work you're doing at Acme Corp, especially in app development. It caught my attention because it aligns with some of the AI-led transformations we're helping companies implement across similar domains.<br>At Bacancy Technology, we're enabling businesses to unlock value through custom AI solutions — with a focus on real outcomes, not buzzwords. Here's how we typically add value:<br><ul><li><strong>Enhance User Experience</strong>: Build AI-driven personalization to boost engagement.</li><li><strong>Boost Operational Efficiency</strong>: Automate workflows for smoother operations.</li><li><strong>Enable Smarter Decisions</strong>: Integrate analytics for data-backed insights.</li></ul><br>If any of these areas resonate with what you're working on, I'd love to exchange ideas or explore if there's a fit.<br>Would you be open to a short call next week?"
            }}

            Now, generate for this lead:

            subject: [8-12 words: Benefit-focused, personalized, e.g., 'Exploring AI Possibilities for {lead.get('company', 'your company')}' - clear and engaging]

            body: [HTML formatted:  
            <p>Hi {lead.get('name', 'there').split()[0] if lead.get('name') else 'there'},</p>
            <p>I hope you're doing well.</p>
            <p>I'm {user_name} from {org_name}. I came across the exciting work you're doing at {lead.get('company', 'your company')}, especially in [brief mention of industry/domain from website {lead.get('company_website', '')} or role {lead.get('role', 'Unknown')}]. It caught my attention because it aligns with some of the AI-led transformations we're helping companies implement across similar domains.</p>
            <p>At {org_name}, we're enabling businesses to unlock value through custom AI solutions — with a focus on real outcomes, not buzzwords. Here's how we typically add value:</p>
            <ul>
            <li><strong>Enhance User Experience</strong>: [Benefit tied to lead, e.g., 'We build AI-driven personalization layers that improve user engagement and retention for {lead.get('company', 'your company')}'s apps.']</li>
            <li><strong>Boost Operational Efficiency</strong>: [Benefit, e.g., 'From automating internal workflows to improving QA/testing cycles, our AI tools streamline {lead.get('role', 'your team')}'s day-to-day.']</li>
            <li><strong>Enable Smarter Decisions</strong>: [Benefit, e.g., 'We help {lead.get('company', 'your company')} make data-backed decisions with intelligent analytics and forecasting models.']</li>
            </ul>
            <p>[Wrap-up: 1-2 sentences, e.g., 'If any of these areas resonate with what you're working on, I'd love to exchange ideas or explore if there's a fit.']</p>
            <p>[CTA: 1-2 sentences: Non-pushy, e.g., 'Would you be open to a short call sometime next week to discuss where AI might make the biggest impact for {lead.get('company', 'your company')}?']</p>]

            Lead Details:
            - Name: {lead.get('name', 'Unknown')}
            - Role: {lead.get('role', 'Unknown')}
            - Company: {lead.get('company', 'Unknown')}
            - Location: {lead.get('location', 'Unknown')}
            - Experience: {lead.get('experience', '')}
            - Company Website: {lead.get('company_website', '')}

            Tone: Professional, warm, conversational—like a peer from India. Short sentences, no sales clichés ('significant value', 'game-changer'). Personalize to lead's details, infer industry from website or role (e.g., for BreakthroughApps.io, use 'wellness app development for meditation, fitness, and nutrition'). Ban: From, To, email addresses, links except lead's website if relevant.
            """

            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.1)
                )
                
                email_content = response.text.strip("```json").strip("```").strip()
                
                print(email_content)

                # Parse JSON
                email_draft = json.loads(email_content)
                subject = email_draft.get("subject", "Personalized AI Outreach")
                body = email_draft.get("body", "Default body with CTA included.")
                
                # Append signature manually
                body += signature
                
                lead["email_draft"] = {
                    "subject": subject,
                    "body": body
                }
            except Exception as e:
                logger.error(f"Error generating or parsing email: {e}", exc_info=True)
                lead["email_draft"] = {
                    "subject": f"Exploring AI for {lead.get('company', 'your company')}",
                    "body": f"<p>Hi {lead.get('name', 'there').split()[0] if lead.get('name') else 'there'},</p><p>I hope you're doing well.</p><p>I'm {user_name} from {org_name}. Let's discuss AI opportunities.</p><p>Would you be open to a call?</p>" + signature
                }

            try:
                with open(f"outputs/email/{lead.get('profile_url', 'unknown').replace('/', '_')}.json", "w") as f:
                    json.dump(lead["email_draft"], f, indent=2)
            except Exception as e:
                logger.error(f"Error saving email draft: {e}", exc_info=True)
        print(f"[{datetime.datetime.now()}] Completed email_writer: Emails generated for {len(leads)} leads")
        return {"leads": leads}