import os
import json
import logging
import asyncio
from datetime import datetime
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import Agents
from agents.custom_lead_discovery import CustomLeadDiscoveryAgent
from agents.lead_enricher import LeadEnricherAgent
from agents.email_writer import EmailWriterAgent
from agents.outreach_executor import OutreachExecutorAgent
from agents.email_reviewer import EmailReviewerAgent
from agents.proposal_generator import ProposalGeneratorAgent
from agents.calendar_manager import CalendarManagerAgent
from agents.reporter import ReporterAgent
from agents.meeting_reporter import MeetingReporter

# Define langgraph state
class AgentState(TypedDict, total=False):
    leads: List[dict]
    search_query: str
    organization_name: str
    user_name: str
    company_email: str
    company_website: str
    company_linkedin: str
    company_logo: str
    num_profiles: int
    email_reviews: List[dict]


# Initialize all agents
custom_lead_discovery = CustomLeadDiscoveryAgent()
lead_enricher = LeadEnricherAgent()
email_writer = EmailWriterAgent()
outreach_executor = OutreachExecutorAgent()
email_reviewer = EmailReviewerAgent()
proposal_generator = ProposalGeneratorAgent()
calendar_manager = CalendarManagerAgent()
reporter = ReporterAgent()
meeting_reporter = MeetingReporter()

leads_file = "outputs/final_leads.json"

# Load lead from file if exists
async def load_leads(state: AgentState) -> AgentState:
    os.makedirs("outputs/email", exist_ok=True)
    os.makedirs("outputs/proposals", exist_ok=True)
    os.makedirs("outputs/replied", exist_ok=True)
    os.makedirs("outputs/non_replied", exist_ok=True)

    if os.path.exists(leads_file) and os.path.getsize(leads_file) > 0:
        with open(leads_file, "r") as f:
            state["leads"] = json.load(f)
        logger.info(f"[{datetime.now()}] Loaded {len(state['leads'])} previous leads from {leads_file}")
    else:
        logger.info(f"[{datetime.now()}] JSON file is blank or not found. Skipping review/proposal/calendar/reporter.")
        state["leads"] = []

    return state

# Condition check
async def check_leads_exist(state: AgentState) -> str:
    return "review_pipeline" if state.get("leads") else "discovery_pipeline"

# Agent wrappers
async def run_email_reviewer(state: AgentState) -> AgentState:
    return await email_reviewer.run(state)

async def run_proposal_generator(state: AgentState) -> AgentState:
    return await proposal_generator.run(state)

async def run_calendar_manager(state: AgentState) -> AgentState:
    return await calendar_manager.run(state)

async def run_reporter(state: AgentState) -> AgentState:
    return await reporter.run(state)

async def run_custom_lead_discovery(state: AgentState) -> AgentState:
    new_state = await custom_lead_discovery.run(state)
    new_leads = new_state.get("leads", [])
    existing_urls = {lead.get("profile_url", "") for lead in state.get("leads" , [])}
    new_unique_leads = [lead for lead in new_leads if lead.get("profile_url", "") not in existing_urls]
    state.setdefault("leads", []).extend(new_unique_leads)
    logger.info(f"[{datetime.now()}] Added {len(new_unique_leads)} new unique leads")
    return state

async def run_lead_enricher(state: AgentState) -> AgentState:
    return await lead_enricher.run(state)

async def run_email_writer(state: AgentState) -> AgentState:
    return await email_writer.run(state)

async def run_outreach_executor(state: AgentState) -> AgentState:
    result = await outreach_executor.run(state)
    with open(leads_file, "w") as f:
        json.dump(state["leads"], f, indent=2)
    logger.info(f"[{datetime.now()}] pipeline completed, leads saved to {leads_file}")
    return result

async def run_report_of_meeting(state: AgentState) -> AgentState:
    return await meeting_reporter.run(state)

# Building LangGraph
builder = StateGraph(AgentState)

# Langgraph Nodes
builder.set_entry_point("load")
builder.add_node("load", load_leads)
builder.add_node("email_review", run_email_reviewer)
builder.add_node("lead_discovery", run_custom_lead_discovery)
builder.add_node("proposal", run_proposal_generator)
builder.add_node("calendar", run_calendar_manager)
builder.add_node("report", run_reporter)
builder.add_node("enrich", run_lead_enricher)
builder.add_node("write_email", run_email_writer)
builder.add_node("execute_outreach", run_outreach_executor)
builder.add_node("reporter", run_reporter)
builder.add_node("meeting_reporter", run_report_of_meeting)

# Langgraph edges
builder.add_conditional_edges("load", check_leads_exist, {
    "review_pipeline": "email_review",
    "discovery_pipeline": "lead_discovery"
})
builder.add_edge("email_review", "calendar") 
builder.add_edge("calendar", "meeting_reporter")
builder.add_edge("meeting_reporter", "lead_discovery") 
builder.add_edge("lead_discovery", "enrich")
builder.add_edge("enrich", "write_email")
builder.add_edge("write_email", "execute_outreach")
builder.add_edge("execute_outreach", "reporter")
builder.add_edge("reporter", END)

# compile graph
graph = builder.compile()

# Run
async def main():
    state: AgentState = {
        "search_query": "AI CEO",
        "organization_name": "Bacancy",
        "user_name": "Dipak Bundheliya",
        "company_email": "dipak.bundheliya@bacancy.com",
        "company_website": "https://www.bacancytechnology.com/",
        "company_linkedin": "https://www.linkedin.com/company/bacancy-technology/",
        "company_logo": "logo.png",
        "num_profiles": 2,
        "email_reviews": []
    }
    start_time = datetime.now()
    await graph.ainvoke(state)
    end_time = datetime.now()
    logger.info(f"Total execution time: {(end_time - start_time).total_seconds():.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())