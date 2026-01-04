from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pandas as pd
from sheets import get_client, SHEET_URL
from datetime import datetime, timedelta
import logging
import asyncio
import os

# --- CONFIG ---
CACHE_DURATION_SECONDS = 60 # Cache data for 1 minute
CACHE = {"data": None, "timestamp": None}

app = FastAPI(title="Grievance Monitoring API")

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
    if os.path.exists("dashboard/dist/index.html"):
        return FileResponse("dashboard/dist/index.html")
    return {"message": "Dashboard Build Not Found. Run 'npm run build' in dashboard/ folder."}

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
        # Ensure numeric Lat/Long
        df['Lat'] = pd.to_numeric(df['Lat'], errors='coerce')
        df['Long'] = pd.to_numeric(df['Long'], errors='coerce')
        
        CACHE["data"] = df
        CACHE["timestamp"] = now
        logger.info("Cache refreshed from Google Sheets")
        return df
    except Exception as e:
        logger.error(f"Data Fetch Error: {e}")
        # If fetch fails but we have old cache, return it even if expired
        if CACHE["data"] is not None:
            return CACHE["data"]
        raise HTTPException(status_code=500, detail="Failed to fetch data")

# --- ENDPOINTS ---

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
