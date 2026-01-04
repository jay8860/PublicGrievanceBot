import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import logging
from datetime import datetime

# --- CONFIGURATION ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1d0a0lfbMyqFJpnn45kC5jZO2uQbcQkrcHlAF_yaP7qA/edit?usp=sharing"
CREDENTIALS_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS") # User must set this in Railway

# Setup Logging
logger = logging.getLogger(__name__)

def get_client():
    """Authenticates with Google Sheets using Service Account."""
    if not CREDENTIALS_JSON:
        logger.error("GOOGLE_SHEETS_CREDENTIALSEnv Var not found!")
        return None
    
    try:
        creds_dict = json.loads(CREDENTIALS_JSON)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        logger.error(f"Auth Error: {e}")
        return None

def log_ticket(ticket_data):
    """
    Logs a new ticket to the Google Sheet.
    ticket_data format:
    {
        "ticket_id": "TKT-123",
        "category": "Roads",
        "severity": "High",
        "description": "...",
        "lat": 12.34,
        "long": 56.78,
        "officer": "Officer_X",
        "photo_url": "...",
        "map_link": "..."
    }
    """
    client = get_client()
    if not client:
        return False

    try:
        sheet = client.open_by_url(SHEET_URL).sheet1
        
        # Ensure Headers Exist
        headers = ["Ticket ID", "Timestamp", "Category", "Severity", "Status", "Officer", "Description", "Lat", "Long", "Photo URL", "Map Link", "Integrity Metric"]
        if sheet.row_values(1) != headers:
            # If empty or wrong, set headers (Optional: check if first row is empty)
            if not sheet.row_values(1): 
                sheet.insert_row(headers, 1)

        # Prepare Row
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            ticket_data.get("ticket_id"),
            timestamp,
            ticket_data.get("category"),
            ticket_data.get("severity"),
            "Open", # Default Status
            ticket_data.get("officer"),
            ticket_data.get("description"),
            ticket_data.get("lat"),
            ticket_data.get("long"),
            ticket_data.get("photo_url", "N/A"),
            ticket_data.get("map_link"),
            "Validated" # Default Integrity
        ]
        
        sheet.append_row(row)
        logger.info(f"Ticket {ticket_data.get('ticket_id')} logged to Sheets.")
        return True
    except Exception as e:
        logger.error(f"Sheet Write Error: {e}")
        return False
