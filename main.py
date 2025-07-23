# main.py
import asyncio
import json
import os
from typing import Dict, List
from datetime import datetime
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import agents
from agents.custom_lead_discovery import CustomLeadDiscoveryAgent
from agents.lead_enricher import LeadEnricherAgent
from agents.email_writer import EmailWriterAgent
from agents.outreach_executor import OutreachExecutorAgent
from agents.email_reviewer import EmailReviewerAgent
from agents.proposal_generator import ProposalGeneratorAgent
# Removed follow_up import as functionality is merged into email_reviewer
from agents.calendar_manager import CalendarManagerAgent
from agents.reporter import ReporterAgent

async def main():
    # Create output directories
    os.makedirs("outputs/emails", exist_ok=True)
    os.makedirs("outputs/proposals", exist_ok=True)
    os.makedirs("outputs/replied", exist_ok=True)
    os.makedirs("outputs/non_replied", exist_ok=True)

    # Initial state
    state: Dict = {
        "leads": [],  # Will be populated by discovery or load
        "search_query": "AI CEO",  # Example query for discovery
        "organization_name": "Bacancy",
        "user_name": "John Doe",
        "company_email": "ronak.h.patel@bacancy.com",
        "company_website": "https://www.bacancytechnology.com/",
        "company_linkedin": "https://www.linkedin.com/company/bacancy-technology/ ",
        "company_logo": "https://assets.bacancytechnology.com/main-boot-5/images/bacancy-logo-white.svg",
        "email_reviews": [],  # Populated by reviewer
    }

    # Instantiate all agents at the beginning
    custom_lead_discovery = CustomLeadDiscoveryAgent()
    lead_enricher = LeadEnricherAgent()
    email_writer = EmailWriterAgent()
    outreach_executor = OutreachExecutorAgent()
    email_reviewer = EmailReviewerAgent()
    proposal_generator = ProposalGeneratorAgent()
    # Removed follow_up instantiation as functionality is merged into email_reviewer
    calendar_manager = CalendarManagerAgent()
    reporter = ReporterAgent()

    leads_file = "outputs/final_leads.json"
    leads_exist = os.path.exists(leads_file) and os.path.getsize(leads_file) > 0  # Check if file exists and not blank

    if leads_exist:
        with open(leads_file, "r") as f:
            state["leads"] = json.load(f)
        logger.info(f"[{datetime.now()}] Loaded {len(state['leads'])} previous leads from {leads_file}")
        
        # If leads exist, run email reviewer (which now includes follow-up), proposal, calendar, reporter
        state.update(await email_reviewer.run(state))
        # Removed follow_up.run as merged
        state.update(await proposal_generator.run(state))
        state.update(await calendar_manager.run(state))
        state.update(await reporter.run(state))
    else:
        logger.info(f"[{datetime.now()}] JSON file is blank or not found. Skipping review/proposal/calendar/reporter.")

    # Always run lead discovery, enrich, write, execute outreach (even if leads exist, but new leads will be added)
    logger.info(f"[{datetime.now()}] Starting lead discovery")
    new_state = await custom_lead_discovery.run(state)
    new_leads = new_state.get("leads", [])

    # Merge new leads, avoiding duplicates by profile_url
    existing_urls = {lead.get("profile_url", "") for lead in state["leads"]}
    new_unique_leads = [lead for lead in new_leads if lead.get("profile_url", "") not in existing_urls]
    state["leads"].extend(new_unique_leads)
    logger.info(f"[{datetime.now()}] Added {len(new_unique_leads)} new unique leads")

    # Process enrich, write, send for the updated leads list
    state.update(await lead_enricher.run(state))
    state.update(await email_writer.run(state))
    state.update(await outreach_executor.run(state))

    # Save updated state
    with open(leads_file, "w") as f:
        json.dump(state["leads"], f, indent=2)

    logger.info(f"[{datetime.now()}] Pipeline completed. Updated leads saved to {leads_file}")

if __name__ == "__main__":
    start_execution_time = time.time()
    asyncio.run(main())
    end_execution_time = time.time()
    logger.info(f"Total execution time for run full pipeline: {end_execution_time - start_execution_time:.2f} seconds")