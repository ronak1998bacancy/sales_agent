# calendar_manager.py
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Dict
from dotenv import load_dotenv
import os, json
import datetime as dt
import logging
import dateutil.parser
import pytz  # For timezone handling
from datetime import timedelta  # For adding duration

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')  # Enhanced to DEBUG
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class CalendarManagerAgent:
    name = "calendar_manager"
    description = "Manages calendar for meeting scheduling and overlap checks"
    input_schema = {"leads": List[Dict]}
    output_schema = {"leads": List[Dict]}

    def __init__(self):
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify',  # Added consistency with email_reviewer
            'https://www.googleapis.com/auth/calendar'
        ]
        self.credentials_path = os.getenv("GOOGLE_OAUTH_CREDENTIALS_PATH")
        self.token_path = 'token.json'
        self.service = self.get_calendar_service()

    def get_calendar_service(self):
        try:
            creds = None
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        logger.info("Refreshed existing token")
                        with open(self.token_path, 'w') as token:  # Save again
                            token.write(creds.to_json())
                    except Exception as e:
                        logger.warning(f"Failed to refresh token: {str(e)}. Initiating new authentication.")
                        creds = None
                if not creds:
                    if not os.path.exists(self.credentials_path):
                        raise FileNotFoundError(f"Credentials file not found at {self.credentials_path}")
                    with open(self.credentials_path, 'r') as f:
                        import json
                        creds_info = json.load(f)
                        if 'installed' not in creds_info:
                            raise ValueError("Credentials JSON must be OAuth 2.0 client type with 'installed' key")
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.scopes)
                    creds = flow.run_local_server(port=0)
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            service = build('calendar', 'v3', credentials=creds)
            # Test service
            service.calendars().get(calendarId='primary').execute()
            logger.info("Calendar API initialized successfully")
            return service
        except HttpError as e:
            logger.error(f"Error initializing Calendar API: {str(e)}. Ensure Calendar API is enabled and scope https://www.googleapis.com/auth/calendar is authorized.", exc_info=True)  # Added exc_info
            return None
        except Exception as e:
            logger.error(f"Unexpected error initializing Calendar API: {str(e)}", exc_info=True)
            return None

    def save_leads_state(self, leads):
        """
        Saves the updated leads state to final_leads.json immediately.
        """
        leads_file = "outputs/final_leads.json"
        try:
            with open(leads_file, "w") as f:
                json.dump(leads, f, indent=2)
            logger.info(f"Updated leads saved to {leads_file} after processing")
        except Exception as e:
            logger.error(f"Error saving leads state: {e}", exc_info=True)

    async def run(self, state):
        logger.info(f"[{dt.datetime.now()}] Starting calendar_manager")
        if self.service is None:
            logger.warning("Calendar service not available. Skipping calendar management.")
            return {"leads": state.get("leads", [])}
        
        leads = state.get("leads", [])
        managed_count = 0
        tz_map = {'IST': 'Asia/Kolkata', 'UTC': 'UTC'}  # Mapping for common timezones
        
        for lead in leads:
            review = lead.get("email_review", {})
            analysis = review.get("analysis", {})
            if review.get("status") == "replied" and analysis.get("interest") == "interested" and not lead.get("meeting_scheduled", False):
                meeting_details = analysis.get("meeting_details")
                try:
                    if meeting_details and meeting_details.get("start") and meeting_details.get("end"):
                        start_details = meeting_details.get("start", {})
                        end_details = meeting_details.get("end", {})
                        proposed_start = dateutil.parser.parse(start_details.get("dateTime", "")) if start_details.get("dateTime") else None
                        proposed_end = dateutil.parser.parse(end_details.get("dateTime", "")) if end_details.get("dateTime") else None
                        timezone_str = start_details.get("timeZone", "UTC")
                        timezone_str = tz_map.get(timezone_str, 'UTC')  # Map ambiguous timezones
                        tz = pytz.timezone(timezone_str)
                        if proposed_start:
                            proposed_start = tz.localize(proposed_start).astimezone(pytz.UTC)
                        if proposed_end:
                            proposed_end = tz.localize(proposed_end).astimezone(pytz.UTC)
                    else:
                        raise ValueError("No meeting details")
                except Exception as e:
                    logger.warning(f"Invalid meeting details format for lead {lead.get('profile_url', 'N/A')}. Error: {e}. Using default.", exc_info=True)
                    proposed_start = dt.datetime.now(pytz.UTC) + dt.timedelta(days=1)
                    proposed_start = proposed_start.replace(hour=10, minute=0, second=0, microsecond=0)
                    proposed_end = proposed_start + dt.timedelta(minutes=30)
                
                if self.check_overlap(proposed_start, proposed_end):
                    event = self.create_meeting_event(lead, proposed_start, proposed_end)
                    if event:  # Check if created successfully
                        lead["meeting"] = event  # Store full JSON schema response
                        lead["meeting_scheduled"] = True
                        managed_count += 1
                        logger.info(f"Scheduled 30-min meeting for lead {lead.get('profile_url', 'unknown')}: {event}")
                        self.save_leads_state(leads)  # Save after successful scheduling
                    else:
                        logger.error(f"Failed to create meeting for lead {lead.get('profile_url', 'unknown')}")
                else:
                    lead["meeting"] = {"status": "overlap", "note": "Reschedule needed"}
                    logger.info(f"Meeting overlap for lead {lead.get('profile_url', 'unknown')}")
                    self.save_leads_state(leads)  # Save even on overlap
        logger.info(f"[{dt.datetime.now()}] Completed calendar_manager: Meetings managed for {managed_count} leads")
        return {"leads": leads}

    def check_overlap(self, start_time, end_time):
        # Format time_min and time_max correctly for UTC: remove tz offset and add 'Z'
        time_min = start_time.replace(tzinfo=None).isoformat() + 'Z'
        time_max = end_time.replace(tzinfo=None).isoformat() + 'Z'
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True
            ).execute()
            events = events_result.get('items', [])
            return len(events) == 0  # No overlap if empty
        except HttpError as e:
            logger.error(f"Error checking calendar overlap: {str(e)}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking calendar: {str(e)}", exc_info=True)
            return False

    def create_meeting_event(self, lead, start_time, end_time):
        event = {
            'summary': f"Meeting with {lead.get('name', 'Lead')} for {lead.get('role', 'Discussion')}",
            'location': 'Online (Google Meet)',
            'description': 'Discussion based on lead reply.',
            'start': {
                'dateTime': start_time.replace(tzinfo=None).isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.replace(tzinfo=None).isoformat(),
                'timeZone': 'UTC',
            },
            'attendees': [{'email': lead.get('email', 'lead@example.com')}],
            'conferenceData': {
                'createRequest': {
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                    'requestId': f"meeting-{dt.datetime.now().timestamp()}"
                }
            }
        }
        try:
            event = self.service.events().insert(
                calendarId='primary',
                body=event,
                sendUpdates='all',
                conferenceDataVersion=1
            ).execute()
            return event
        except HttpError as e:
            logger.error(f"Error creating event: {str(e)}", exc_info=True)
            return {}
        except Exception as e:
            logger.error(f"Unexpected error creating event: {str(e)}", exc_info=True)
            return {}