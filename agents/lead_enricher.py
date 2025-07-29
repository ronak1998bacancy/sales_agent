# lead_enricher.py
from typing import List, Dict
import requests
from dotenv import load_dotenv
import os
import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class LeadEnricherAgent:
    name = "lead_enricher"
    description = "Enriches leads with contact data using Hunter.io"
    input_schema = {"leads": List[Dict]}
    output_schema = {"leads": List[Dict]}  # Update same leads list

    def __init__(self):
        self.hunter_api_key = os.getenv("HUNTER_API_KEY")

    async def run(self, state):
        print(f"[{datetime.datetime.now()}] Starting lead_enricher")
        leads = state.get("leads", [])
        for lead in leads:
            if lead.get("email"):
                continue  
            try:
                company_website = lead.get("company_website")
                name_list = lead.get('name', "").split(" ")
                if name_list:
                    first_name = name_list[0]
                    last_name = name_list[1]
                else : 
                    first_name = ""
                    last_name = ""
                response = requests.get(
                    f"https://api.hunter.io/v2/email-finder?domain={company_website}&first_name={first_name}&last_name={last_name}&api_key={self.hunter_api_key}"
                )
                data = response.json().get("data", {})
                if response.status_code != 200:
                    email = "pitaji.injala@gmail.com"
                else:
                    email = data.get("emails", [{}])[0].get("value", "unknown@example.com")
            except requests.RequestException as e:
                logger.error(f"Error enriching lead with Hunter.io: {e}", exc_info=True)
                email = "pitaji.injala@gmail.com"  # Changed fallback to generic
            lead["email"] = email

        # Print information about newly generated emails (those without email_sent flag)
        new_emails = [lead for lead in leads if not lead.get("email_sent", False)]
        print(f"[{datetime.datetime.now()}] Completed lead_enricher: {len(new_emails)} leads enriched")
        return {"leads": leads}