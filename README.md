# Sales Agent AI Assistant

This project is an intelligent, automated sales agent that handles end-to-end outreach to potential clients. It scrapes data from LinkedIn, identifies CEO/CTO profiles, finds their emails, sends personalized cold emails, observes their responses, and schedules meetings if they are interested. It also generates a report summarizing all activities, including how many leads were contacted, how many replied, and who scheduled a meeting.

## How the Flow Works

- Scrape LinkedIn for people matching a search term (e.g., CEO, CTO).
- Extract email using Hunter API based on name and domain.
- Compose and send cold emails offering services.
- Use Gmail API to observe replies.
- If the lead is interested:
  - Analyze their reply using DeepSeek (LLM).
  - Schedule a Google Calendar meeting.
  - Send a polite confirmation.
- If not interested, send a polite thank-you email.
- Generate a report showing:
  - Number of leads found and emailed.
  - List of people who showed interest with meeting time and link.

## How to Run the Project

1. Clone the repository:
```bash
git clone https://github.com/ronak1998bacancy/sales_agent
cd sales_agent
```

2. Install required Python packages:
```bash
pip install -r requirements.txt
```

3. Set up your environment file:
Create a `.env` file in the root directory of the project. You can use `.env.example` as a template:
```bash
cp .env.example .env
```

Fill in the `.env` with your actual credentials:
```env
# Hunter API key to find emails
HUNTER_API_KEY=your_hunter_api_key

# LinkedIn login for scraping
LINKEDIN_EMAIL=your_linkedin_email
LINKEDIN_PASSWORD=your_linkedin_password

# Email to receive the report
REPORT_EMAIL_ID=your.manager@example.com

# DeepSeek API key to classify replies
DEEPSEEK_API_KEY=your_deepseek_api_key

# Google credentials (OAuth) and token, you need to setup google cloud console account, OAuth authentication and create Desktop app for use calender api
GOOGLE_OAUTH_CREDENTIALS_PATH=credentials.json

# SMTP details to send emails
SMTP_HOST=smtp.gmail.com
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_email_password

# Google API key (if needed)
GOOGLE_API_KEY=your_google_api_key
```

4. Run the script:
```bash
python main.py
```

## Sample Report Output

- 14 leads found and emailed  
- 3 replied with interest  
- 2 meetings scheduled  
- Meeting links and details added to Google Calendar  
- Report emailed to the configured manager email address

## Notes

- You can use `.env.demo` for sandbox/demo mode.
- Make sure Gmail and Calendar APIs are enabled in your Google Cloud project.
- `token.json` will be generated on first auth and reused afterward.
- Reports are saved in `outputs/` folder.

Project built by Ronak patel and Dipak Bundheliya
