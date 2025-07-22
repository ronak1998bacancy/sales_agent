# main.py
import asyncio
import json
import os
from typing import Dict, List
from datetime import datetime
import logging

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
from agents.follow_up import FollowUpAgent
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
        "search_query": "CTO AI company OR CEO AI startup",  # Example query for discovery
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
    follow_up = FollowUpAgent()
    calendar_manager = CalendarManagerAgent()
    reporter = ReporterAgent()

    leads_file = "outputs/final_leads.json"
    leads_exist = os.path.exists(leads_file)

    if leads_exist:
        with open(leads_file, "r") as f:
            state["leads"] = json.load(f)
        logger.info(f"[{datetime.now()}] Loaded {len(state['leads'])} previous leads from {leads_file}")
        
        # Process existing leads: regular pipeline (review, proposals, meetings, follow-ups, report)
        state.update(await email_reviewer.run(state))
        state.update(await proposal_generator.run(state))
        state.update(await calendar_manager.run(state))
        state.update(await follow_up.run(state))
        state.update(await reporter.run(state))

    # Always discover new leads, regardless of existing ones
    logger.info(f"[{datetime.now()}] Starting lead discovery (always runs)")
    new_state = await custom_lead_discovery.run(state)
    new_leads = new_state.get("leads", [])

    # Merge new leads, avoiding duplicates by profile_url
    existing_urls = {lead.get("profile_url", "") for lead in state["leads"]}
    new_unique_leads = [lead for lead in new_leads if lead.get("profile_url", "") not in existing_urls]
    state["leads"].extend(new_unique_leads)
    logger.info(f"[{datetime.now()}] Added {len(new_unique_leads)} new unique leads")

    # Process the entire updated leads list (enrich, write/send if not done)
    state.update(await lead_enricher.run(state))
    state.update(await email_writer.run(state))
    state.update(await outreach_executor.run(state))

    # Review again for any immediate changes or new leads
    state.update(await email_reviewer.run(state))

    # Save updated state
    with open(leads_file, "w") as f:
        json.dump(state["leads"], f, indent=2)

    logger.info(f"[{datetime.now()}] Pipeline completed. Updated leads saved to {leads_file}")

if __name__ == "__main__":
    asyncio.run(main())