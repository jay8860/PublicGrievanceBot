from fastapi import FastAPI, HTTPException, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import pandas as pd
from sheets import get_client, SHEET_URL, get_officer_map
from datetime import datetime, timedelta
import logging
import asyncio
import os

# Auth Imports
from auth import verify_admin, create_access_token, verify_password

# --- CONFIG ---
CACHE_DURATION_SECONDS = 60 # Cache data for 1 minute
CACHE = {"data": None, "timestamp": None}

app = FastAPI(title="Grievance Monitoring API")

class LoginRequest(BaseModel):
    username: str
    password: str


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for demo/dev
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- SERVE FRONTEND ---
# Mount static files (JS/CSS)
if os.path.exists("dashboard/dist"):
    app.mount("/assets", StaticFiles(directory="dashboard/dist/assets"), name="assets")

@app.get("/")
def read_root():
    """Serves the React Frontend Entry Point."""
    dist_path = "dashboard/dist/index.html"
    if os.path.exists(dist_path):
        return FileResponse(dist_path)
    
    # Debug Info
    cwd = os.getcwd()
    ls = os.listdir(".")
    dash_ls = os.listdir("dashboard") if os.path.exists("dashboard") else "dashboard_not_found"
    return {
        "error": "Dashboard Build Not Found",
        "cwd": cwd,
        "ls_root": ls,
        "ls_dashboard": dash_ls,
        "tip": "Check Build Logs for npm errors."
    }

# --- CACHING LOGIC ---
def get_cached_dataframe():
    """Fetches data from Google Sheets with caching."""
    global CACHE
    now = datetime.now()
    
    # Return cache if valid
    if CACHE["data"] is not None and CACHE["timestamp"]:
        if (now - CACHE["timestamp"]).total_seconds() < CACHE_DURATION_SECONDS:
            return CACHE["data"]

    # Fetch Fresh
    try:
        client = get_client()
        if not client:
            raise Exception("Google Sheets Auth Failed")
            
        sheet = client.open_by_url(SHEET_URL).sheet1
        data = sheet.get_all_records() # Returns list of dicts
        df = pd.DataFrame(data)
        
        # Normalize Columns
        # Expects: Ticket ID, Timestamp, Category, Severity, Status, Officer, Description, Lat, Long, Photo URL, Map Link, Integrity Metric
        if not df.empty and 'Lat' in df.columns and 'Long' in df.columns:
            df['Lat'] = pd.to_numeric(df['Lat'], errors='coerce')
            df['Long'] = pd.to_numeric(df['Long'], errors='coerce')
        
        CACHE["data"] = df
        CACHE["timestamp"] = now
        logger.info("Cache refreshed from Google Sheets")
        return df
    except Exception as e:
        logger.error(f"Data Fetch Error: {e}")
        if CACHE["data"] is not None:
             return CACHE["data"]
        # Allow returning empty DF instead of crashing if persistent error?
        # Better to bubble up so we know it failed, but for Frontend it's better to show empty than crash?
        # Let's re-raise to see error in debug endpoint.
        raise e

# --- ENDPOINTS ---

@app.post("/api/login")
def login(creds: LoginRequest):
    if verify_admin(creds.username, creds.password):
        # Generate Token
        access_token = create_access_token(data={"sub": creds.username})
        return {"access_token": access_token, "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Incorrect username or password")


@app.get("/api/debug_auth")
def debug_auth():
    """Debugs Google Sheets Connection."""
    try:
        client = get_client()
        if not client:
            return {"status": "error", "message": "Client is None. Check Credentials."}
        
        sheet = client.open_by_url(SHEET_URL).sheet1
        data = sheet.get_all_records()
        return {
            "status": "ok", 
            "row_count": len(data),
            "columns": list(data[0].keys()) if data else "No Data",
            "sample": data[:2] if data else []
        }
    except Exception as e:
        import traceback
        return {"status": "error", "detail": str(e), "trace": traceback.format_exc()}


@app.get("/api/stats")
def get_stats():
    df = get_cached_dataframe()
    total = len(df)
    
    # Status Counts
    if 'Status' in df.columns:
        status_counts = df['Status'].value_counts().to_dict()
    else:
        status_counts = {}
        
    resolved = status_counts.get("Resolved", 0)
    open_tickets = total - resolved
    
    return {
        "total": int(total),
        "open": int(open_tickets),
        "resolved": int(resolved),
        "breakdown": status_counts
    }

@app.get("/api/filters")
def get_filters():
    df = get_cached_dataframe()
    def get_unique(col):
        if col in df.columns:
            return sorted([str(x) for x in df[col].unique() if str(x).strip()])
        return []

    return {
        "categories": get_unique("Category"),
        "severities": get_unique("Severity"),
        "statuses": get_unique("Status"),
        "officers": get_unique("Officer")
    }

@app.get("/api/officers")
def get_officer_details():
    """Returns the Officer Map (SLA, L1, L2 for each Category)."""
    return get_officer_map()

@app.get("/api/works") # Keeping name 'works' to match frontend, or 'grievances'
def get_grievances(
    category: str = Query(None),
    status: str = Query(None),
    severity: str = Query(None),
    officer: str = Query(None),
    search: str = Query(None)
):
    df = get_cached_dataframe().copy()
    
    # Filters
    if category: df = df[df['Category'] == category]
    if status: df = df[df['Status'] == status]
    if severity: df = df[df['Severity'] == severity]
    if officer: df = df[df['Officer'] == officer]
    
    if search:
        # Search in ID, Description, Category
        mask = (
            df['Ticket ID'].astype(str).str.contains(search, case=False, na=False) |
            df['Description'].str.contains(search, case=False, na=False)
        )
        df = df[mask]
    
    # Convert to API format (list of dicts)
    # Handle NaN for JSON serialization
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient='records')

@app.get("/api/locations")
def get_locations():
    """Lightweight endpoint for Map View."""
    df = get_cached_dataframe()
    # Filter valid coordinates
    valid_geo = df.dropna(subset=['Lat', 'Long'])
    
    return [
        {
            "id": row.get("Ticket ID"),
            "lat": row.get("Lat"),
            "lng": row.get("Long"),
            "category": row.get("Category"),
            "severity": row.get("Severity"),
            "status": row.get("Status"),
            "desc": row.get("Description") # Short description for tooltip
        }
        for _, row in valid_geo.iterrows()
    ]
