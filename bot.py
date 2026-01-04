import os
import logging
import asyncio
import hashlib
import time
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import google.generativeai as genai
from PIL import Image
import io
import json

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8577255418:AAF2h6C0ICMs4IuaweH_5OnSNyWOxYCKQQ4")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

# --- TRIAGE CONFIG ---
MAX_REPORTS_PER_HOUR = 100 # Increased for testing
RATE_LIMIT_STORE = {} # {user_id: [timestamp1, timestamp2]}
DUPLICATE_HASHES = set() # Store MD5 hashes of processed images (In-memory for demo)

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')

# --- STATES ---
LOCATION = 1

# --- MOCK DATABASE & OFFICERS ---
# --- MOCK DATABASE & OFFICERS ---
# Officers are now fetched dynamically from Google Sheets

# --- HELPERS: INTEGRITY CHECKS ---

def check_rate_limit(user_id: int) -> bool:
    """Returns True if user is allowed, False if rate limited."""
    now = time.time()
    history = RATE_LIMIT_STORE.get(user_id, [])
    # Keep only timestamps within last 1 hour (3600 seconds)
    valid_history = [t for t in history if now - t < 3600]
    
    if len(valid_history) >= MAX_REPORTS_PER_HOUR:
        return False
    
    valid_history.append(now)
    RATE_LIMIT_STORE[user_id] = valid_history
    return True

def get_image_hash(image_bytes: bytes) -> str:
    """Returns MD5 hash of image bytes for duplicate detection."""
    return hashlib.md5(image_bytes).hexdigest()

# --- BOT FUNCTIONS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: # Changed return type for consistency
    """Send a welcome message."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! \n\n"
        "I am the <b>Public Grievance AI Bot</b>. 🤖\n"
        "Please <b>send me a photo</b> of the issue (e.g., Pothole, Garbage, Broken Light) and I will route it to the correct officer.",
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text("Process cancelled. Send /start to try again.")
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message."""
    await update.message.reply_text("Just send a photo of the grievance! I'll handle the rest.")

async def analyze_image_with_bouncer(image_bytes):
    """Sends image to Gemini for Triage (Relevance Check) + Analysis."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # PROMPT: acts as the "Bouncer"
        prompt = """
        Analyze this image strictly for a Public Grievance System.
        
        Phase 1: FORENSIC & RELEVANCE CHECK (The Bouncer)
        
        1. ANTI-SPOOFING CHECK (Digital Screen Detection):
           - Look closely for **Moiré patterns** (wavy interference lines typical when photographing screens).
           - Look for **visible pixel grids** or RGB sub-pixels.
           - Look for **Screen Bezels**, monitor frames, or laptop edges bordering the image.
           - IF ANY OF ABOVE FOUND -> REJECT immediately. Reason: "Photo of a digital screen detected."

        2. CONTENT RELEVANCE CHECK:
           - Is this a REAL LIFE photo of a public infrastructure issue (pothole, garbage, broken light, water leak)?
           - REJECT IF: Selfie, meme, screenshot, text document, blurry/unclear, indoor residential, or unrelated object.
        
        - Return "is_valid": false if rejected by either check.

        Phase 2: ANALYSIS (If Valid)
        - Identify Category: [Roads, Sanitation, Electricity, Water, Other] (Map Pothole->Roads, Garbage->Sanitation etc)
        - Severity: [High, Medium, Low]
        - Description: 1 sentence summary.

        OUTPUT FORMAT: JSON ONLY
        {
            "is_valid": boolean,
            "rejection_reason": "string (only if false, strictly polite)",
            "category": "string",
            "severity": "string",
            "description": "string"
        }
        """
        
        response = model.generate_content([prompt, image], generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return None

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 1: Triage -> Analyze -> Ask Location."""
    user = update.effective_user
    
    # Check 1: Rate Limiting
    if not check_rate_limit(user.id):
        await update.message.reply_text("⚠️ <b>Rate Limit Exceeded.</b>\nYou have sent too many reports recently. Please try again in an hour.", parse_mode='HTML')
        return ConversationHandler.END

    status_msg = await update.message.reply_text("🧐 Analyzing and validating your photo... Please wait.")
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Check 2: Duplicate Detection
        img_hash = get_image_hash(photo_bytes)
        if img_hash in DUPLICATE_HASHES:
            await status_msg.edit_text("⚠️ <b>Duplicate Detected.</b>\nWe have already processed this exact photo.", parse_mode='HTML')
            return ConversationHandler.END
        
        # 3. Analyze with "Bouncer"
        analysis = await analyze_image_with_bouncer(photo_bytes)
        
        if not analysis:
            await status_msg.edit_text("❌ Technical Error analyzing image. Please try again.")
            return ConversationHandler.END

        # Check 3: AI Relevance
        if not analysis.get("is_valid", False):
            reason = analysis.get("rejection_reason", "Image does not appear to be a public grievance.")
            await status_msg.edit_text(f"❌ <b>Image Rejected</b>\n\n{reason}\n\n<i>Please upload a clear photo of a public infrastructure issue.</i>", parse_mode='HTML')
            return ConversationHandler.END

        # If Valid -> Mark hash as processed
        DUPLICATE_HASHES.add(img_hash)
        context.user_data['analysis'] = analysis # Store JSON

        # 4. Ask for Location
        location_keyboard = [[KeyboardButton(text="📍 Share Current Location", request_location=True)]]
        reply_markup = ReplyKeyboardMarkup(location_keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await status_msg.edit_text(
            f"✅ <b>Issue Verified: {analysis['category']}</b>\n\n"
            f"📝 {analysis['description']}\n\n"
            "📍 <b>Step 2:</b> Please share your **Location** to finalize.",
            parse_mode='HTML'
        )
        await update.message.reply_text("Click below to share location 👇", reply_markup=reply_markup)
        
        return LOCATION

    except Exception as e:
        logging.error(f"Handler Error: {e}")
        await status_msg.edit_text("❌ Something went wrong.")
        return ConversationHandler.END

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Receives location and finalizes ticket."""
    user_location = update.message.location
    lat = user_location.latitude
    lon = user_location.longitude
    accuracy = user_location.horizontal_accuracy
    
    # Accuracy Check
    if accuracy is not None and accuracy > 25:
        await update.message.reply_text(
            f"⚠️ <b>Low GPS Accuracy detected ({accuracy:.1f}m).</b>\nWait for GPS to lock and <b>Share Location again</b>.",
            parse_mode='HTML'
        )
        return LOCATION

    # Retrieve valid analysis
    analysis = context.user_data.get('analysis', {})
    category = analysis.get('category', 'Other')
    severity = analysis.get('severity', 'Medium')
    description = analysis.get('description', 'No description available.')
    
    description = analysis.get('description', 'No description available.')
    
    # Dynamic Officer Lookup
    from sheets import get_officer_map, log_ticket
    officer_map = get_officer_map()
    
    # Default to General Admin if category not found or officer not set
    category_data = officer_map.get(category, {})
    assigned_officer = category_data.get("L1", "General_Admin")
    
    map_link = f"https://www.google.com/maps?q={lat},{lon}"
    ticket_id = f"TKT-{update.message.message_id}"
    
    # --- LOG TO SHEETS ---
    ticket_data = {
        "ticket_id": ticket_id,
        "category": category,
        "severity": severity,
        "description": description,
        "lat": lat,
        "long": lon,
        "officer": assigned_officer,
        "photo_url": "N/A", # Telegram URLs expire, requires more logic to host. Using N/A for now.
        "map_link": map_link
    }
    # Run in background so it doesn't block the bot
    asyncio.create_task(asyncio.to_thread(log_ticket, ticket_data))
    
    response_text = (
        f"✅ <b>Ticket Registered Successfully!</b>\n\n"
        f"📂 <b>Category:</b> {category}\n"
        f"⚠️ <b>Severity:</b> {severity}\n"
        f"👮 <b>Assigned To:</b> {assigned_officer}\n"
        f"📍 <b>Location:</b> <a href='{map_link}'>View on Map</a>\n"
        f"🎯 <b>Accuracy:</b> {accuracy}m\n"
        f"🎫 <b>Ticket ID:</b> #{ticket_id}\n\n"
        f"<i>We have notified the designated officer.</i>"
    )
    
    await update.message.reply_html(response_text, reply_markup=None)
    
    return ConversationHandler.END

# --- MAIN ---

def main() -> None:
    """Start the bot."""
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("ERROR: Please update the TELEGRAM_BOT_TOKEN in the script.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Conversation Handler with States
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, handle_photo)],
        states={
            LOCATION: [
                MessageHandler(filters.LOCATION, handle_location),
                MessageHandler(filters.PHOTO, handle_photo) # Allow restarting with new photo
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
