# lead_enricher.py
from typing import List, Dict
import requests
from dotenv import load_dotenv
import os
import datetime

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
        leads = state["leads"]
        for lead in leads:
            company = lead.get("company") or "unknown"  # Handle None or missing
            company_domain = company.lower().replace(" ", "") + ".com"  # Simple domain guess
            response = requests.get(
                f"https://api.hunter.io/v2/domain-search?domain={company_domain}&api_key={self.hunter_api_key}"
            )
            if response.status_code == 200:
                data = response.json()["data"]
                email = data["emails"][0]["value"] if data.get("emails") else "unknown@example.com"
            else:
                email = "pitaji.injala@gmail.com"
            lead["email"] = email
        print(f"[{datetime.datetime.now()}] Completed lead_enricher: {len(leads)} leads enriched")
        return {"leads": leads}