# proposal_generator.py
import jinja2
import pdfkit
from pydantic import BaseModel
from typing import List, Dict
from openai import OpenAI
from dotenv import load_dotenv
import os
import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class Proposal(BaseModel):
    lead_id: str
    proposal_path: str

class ProposalGeneratorAgent:
    name = "proposal_generator"
    description = "Generates proposals for qualified leads"
    input_schema = {"leads": List[Dict]}
    output_schema = {"leads": List[Dict]}  # Update same leads list

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.env = jinja2.Environment()
        # Embed the template as a string instead of loading from external HTML file
        self.template_string = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Statement of Work</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { text-align: center; }
        .section { margin-bottom: 20px; }
    </style>
</head>
<body>
    <h1>Statement of Work</h1>
    <div class="section">
        {{ content }}
    </div>
</body>
</html>
        """
        self.template = self.env.from_string(self.template_string.strip())

    async def run(self, state):
        print(f"[{datetime.datetime.now()}] Starting proposal_generator")
        leads = state.get("leads", [])
        generated_count = 0
        for lead in leads:
            review = lead.get("email_review", {})
            if review.get("status") == "replied" and review.get("client_intent", {}).get("intent") == "proposal_requested" and "proposal" not in lead:  # Skip if already generated
                prompt = f"""
                Generate a 2-page SoW for lead: {lead.get('profile_url', 'unknown')}
                Project: Based on company {lead.get('company', 'N/A')} and experience {lead.get('experience', 'N/A')}
                Use fixed-price model. Include scope, timeline, deliverables.
                """
                try:
                    response = self.client.chat.completions.create(
                        model="gpt-4",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    sow_content = response.choices[0].message.content
                except Exception as e:
                    logger.error(f"Error generating SoW with AI: {e}", exc_info=True)
                    sow_content = "Default SoW content"
                html_content = self.template.render(content=sow_content)
                proposal_path = f"outputs/proposals/{lead.get('profile_url', 'unknown').replace('/', '_')}.pdf"
                try:
                    pdfkit.from_string(html_content, proposal_path)
                    if os.path.exists(proposal_path):
                        generated_count += 1
                        logger.info(f"Proposal stored at {proposal_path}")
                    else:
                        raise FileNotFoundError("PDF not created")
                except Exception as e:
                    logger.error(f"Failed to generate or store proposal: {e}", exc_info=True)
                lead["proposal"] = {
                    "proposal_path": proposal_path
                }
        print(f"[{datetime.datetime.now()}] Completed proposal_generator: Proposals generated for {generated_count} leads")
        return {"leads": leads}