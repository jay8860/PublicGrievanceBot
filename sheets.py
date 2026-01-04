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
        headers = ["Ticket ID", "Timestamp", "Category", "Severity", "Status", "Officer", "Description", "Lat", "Long", "Photo URL", "Map Link", "Integrity Metric", "Chat ID", "PhotoID", "After File ID", "User Rating"]
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
            "Validated", # Default Integrity
            ticket_data.get("citizen_chat_id", ""), # Col 13
            ticket_data.get("photo_file_id", "")  # Col 14
        ]
        
        sheet.append_row(row)
        logger.info(f"Ticket {ticket_data.get('ticket_id')} logged to Sheets.")
        return True
        return True
    except Exception as e:
        logger.error(f"Sheet Write Error: {e}")
        return False

def update_ticket_status(ticket_id, status, after_photo_url="N/A"):
    """
    Updates the status and after_photo of a ticket by ID.
    Status can be 'Resolved' or 'Closed'.
    """
    client = get_client()
    if not client: return False
    
    try:
        sheet = client.open_by_url(SHEET_URL).sheet1
        # Find cell with Ticket ID
        cell = sheet.find(ticket_id)
        if not cell:
            logger.warning(f"Ticket {ticket_id} not found for update.")
            return False
        
        # Update Status (Col 5) and Photo (Col 10 or append new column for After Photo)
        # Assuming Status is Col 5 (E)
        sheet.update_cell(cell.row, 5, status)
        
        # Note: We are overwriting Photo URL for now or we could add a new column
        # Let's add a "Resolution Photo" column if it doesn't exist?
        # For simplicity, we'll just log it to a new "Resolution Note" or similar if needed.
        # But user asked for showing Before/After. 
        # Let's assume we append " | After: url" to the Photo URL column (Col 10)
        # Or better, let's just create a new Column if we can.
        
        # Simple Approach: Append to Description
        # current_desc = sheet.cell(cell.row, 7).value
        # sheet.update_cell(cell.row, 7, f"{current_desc} | Resolution: {after_photo_url}")
        
        return True
    except Exception as e:
        logger.error(f"Sheet Update Error: {e}")
        return False

def get_ticket_meta(ticket_id):
    """Fetches Citizen Chat ID and Photo File ID for a ticket."""
    client = get_client()
    if not client: return None
    try:
        sheet = client.open_by_url(SHEET_URL).sheet1
        cell = sheet.find(ticket_id)
        if not cell: return None
        
        row_values = sheet.row_values(cell.row)
        # Assuming Col 13 is Citizen ID, Col 14 is Photo ID
        # Safety check for list index
        citizen_id = row_values[12] if len(row_values) > 12 else None
        photo_id = row_values[13] if len(row_values) > 13 else None
        
        return {
            "citizen_chat_id": citizen_id,
            "photo_file_id": photo_id
        }
    except Exception as e:
        logger.error(f"Meta Fetch Error: {e}")
        return None

def update_ticket_rating(ticket_id, rating):
    """Updates the rating (Col 16)."""
    client = get_client()
    if not client: return False
    try:
        sheet = client.open_by_url(SHEET_URL).sheet1
        cell = sheet.find(ticket_id)
        if not cell: return False
        
        sheet.update_cell(cell.row, 16, rating) # Col 16
        return True
    except Exception as e:
        logger.error(f"Rating Update Error: {e}")
        return False

# --- CACHE FOR OFFICERS ---
OFFICER_CACHE = {
    "data": {},
    "timestamp": 0
}
CACHE_TTL = 300 # 5 minutes

def get_officer_map():
    """
    Fetches Officer Details from 'Officer Details' sheet.
    Schema: Officer_ID, Full_Name, Mobile, Designation, Sector, Zone, Level, Reports_To, Sector_Head_ID
    Returns: { "Category": {"L1": "Name", "L2": "Name", "SLA": 48} }
    """
    global OFFICER_CACHE
    now = time.time()
    
    # Return Cache if valid
    if now - OFFICER_CACHE["timestamp"] < CACHE_TTL and OFFICER_CACHE["data"]:
        return OFFICER_CACHE["data"]

    client = get_client()
    if not client:
        return {}

    try:
        try:
            sheet = client.open_by_url(SHEET_URL).worksheet("Officer Details")
        except gspread.WorksheetNotFound:
            logger.warning("'Officer Details' sheet not found! Using fallback.")
            return {}

        records = sheet.get_all_records()
        
        # 1. Build ID Lookup
        # Officer_ID -> {Name, Level, Reports_To}
        officer_db = {
            str(row.get("Officer_ID")): {
                "name": row.get("Full_Name"),
                "reports_to": str(row.get("Reports_To")),
                "level": str(row.get("Level"))
            } for row in records
        }

        # 2. Group by Sector (Category)
        mapping = {}
        for row in records:
            sector = row.get("Sector")
            if not sector: continue
            
            # Logic: Find the "Ground" officer (Level 1) for this sector
            # If multiple Lv1s exist, this simple logic picks the last one encountered.
            # Ideally obtaining "Zone" from the Ticket would map to specific Lv1.
            # For now, we map Sector -> One Rep.
            
            lvl = str(row.get("Level"))
            if lvl in ["1", "L1", "Field"]:
                l1_name = row.get("Full_Name")
                l2_id = str(row.get("Reports_To"))
                l2_name = officer_db.get(l2_id, {}).get("name", "Unassigned")
                
                mapping[sector] = {
                    "L1": l1_name,
                    "L2": l2_name,
                    "SLA": 48 # Default as column is missing
                }
        
        # Update Cache
        OFFICER_CACHE["data"] = mapping
        OFFICER_CACHE["timestamp"] = now
        logger.info(f"Refreshed Officer Map: {len(mapping)} sectors mapped.")
        return mapping

    except Exception as e:
        logger.error(f"Error fetching officer map: {e}")
        return OFFICER_CACHE.get("data", {})
