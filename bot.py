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
import requests

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8577255418:AAF2h6C0ICMs4IuaweH_5OnSNyWOxYCKQQ4")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
TEST_OFFICER_CHAT_ID = 579438947 # Hardcoded for Testing
TEST_MODE = True

# --- TRIAGE CONFIG ---
MAX_REPORTS_PER_HOUR = 100 
RATE_LIMIT_STORE = {} 
DUPLICATE_HASHES = set() 

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

    """Returns MD5 hash of image bytes for duplicate detection."""
    return hashlib.md5(image_bytes).hexdigest()

def get_address_details(lat, lon):
    """
    Reverse Geocodes Lat/Lon to get Pin Code and Area.
    Uses OpenStreetMap Nominatim API (Free).
    """
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
        headers = {'User-Agent': 'PublicGrievanceBot/1.0 (jayantnahata@example.com)'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            address = data.get('address', {})
            
            pincode = address.get('postcode', '')
            
            # Smart Area Detection
            # Prefer: Suburb > Neighbourhood > Residential > Village > City District > City
            area = (
                address.get('suburb') or 
                address.get('neighbourhood') or 
                address.get('residential') or
                address.get('village') or
                address.get('city_district') or
                address.get('city') or
                "Unknown Area"
            )
            
            return {"pincode": pincode, "area": area}
    except Exception as e:
        logging.error(f"Geocoding Error: {e}")
    
    return {"pincode": "", "area": ""}

# --- BOT FUNCTIONS ---

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Returns the user's numeric Chat ID."""
    await update.message.reply_text(f"Your Chat ID is: `{update.effective_chat.id}`", parse_mode='Markdown')

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
        - Identify Category: ['Sanitation', 'Drainage', 'Water Supply', 'Road Infra', 'Lighting', 'Fire', 'Other']
        - Map strictly:
          * Garbage/Trash -> Sanitation
          * Pothole/Broken Road -> Road Infra
          * Water Leak/Pipe Burst -> Water Supply
          * Street Light -> Lighting
          * Clogged Drain -> Drainage
          * Fire Hazards -> Fire
          * Else -> Other
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
        
        # Store File ID for later use (Sending to Officer)
        context.user_data['photo_file_id'] = photo_file.file_id
        
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

    analysis = context.user_data.get('analysis', {})
    photo_file_id = context.user_data.get('photo_file_id') # From handle_photo
    category = analysis.get('category', 'Other')
    severity = analysis.get('severity', 'Medium')
    description = analysis.get('description', 'No description available.')
    
    # Dynamic Officer Lookup
    try:
        from sheets import get_officer_map, log_ticket
        officer_map = get_officer_map()
        # ... (Officer Lookup Logic Same)
        category_data = officer_map.get(category, {})
        assigned_officer = category_data.get("L1", "General_Admin")
    except Exception as e:
        logging.error(f"Officer Lookup Failed: {e}")
        assigned_officer = "General_Admin (Fallback)"
    
    map_link = f"https://www.google.com/maps?q={lat},{lon}"
    ticket_id = f"TKT-{update.message.message_id}"
    
    # --- GEOCODING ---
    # Run in thread to avoid blocking? It uses requests (blocking). 
    # Better to run in thread or use async client. 
    # For simplicity/speed in this context, we'll run it synchronously or slightly block.
    # Given it's one call, it's okay, but let's wrap in to_thread for safety.
    geo_info = await asyncio.to_thread(get_address_details, lat, lon)
    
    # --- LOG TO SHEETS ---
    ticket_data = {
        "ticket_id": ticket_id,
        "category": category,
        "severity": severity,
        "description": description,
        "lat": lat,
        "long": lon,
        "officer": assigned_officer,
        "photo_url": "N/A",
        "map_link": map_link,
        "citizen_chat_id": update.effective_chat.id,
        "photo_file_id": photo_file_id,
        "pincode": geo_info.get("pincode"),
        "area": geo_info.get("area")
    }
    # Run in background so it doesn't block the bot
    asyncio.create_task(asyncio.to_thread(log_ticket, ticket_data))
    
    # --- NOTIFY OFFICER (Test Mode) ---
    if TEST_MODE and TEST_OFFICER_CHAT_ID:
        try:
            officer_msg = (
                f"🚨 <b>New Grievance Assigned!</b>\n"
                f"🎫 <b>Ticket:</b> #{ticket_id}\n"
                f"📂 <b>Category:</b> {category}\n"
                f"📍 <b>Area:</b> {geo_info.get('area')} ({geo_info.get('pincode')})\n"
                f"📝 <b>Desc:</b> {description}\n\n"
                f"👉 <b>Action:</b> Reply to this message with a <b>PHOTO</b> to mark as RESOLVED."
            )
            # Send PHOTO + Caption
            if photo_file_id:
                await context.bot.send_photo(chat_id=TEST_OFFICER_CHAT_ID, photo=photo_file_id, caption=officer_msg, parse_mode='HTML')
            else:
                await context.bot.send_message(chat_id=TEST_OFFICER_CHAT_ID, text=officer_msg, parse_mode='HTML')
                
        except Exception as e:
            logging.error(f"Failed to notify officer: {e}")

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

async def handle_officer_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles Officer's Reply (Photo) to Close Ticket."""
    msg = update.message
    
    # Check if this is a reply to a bot message
    if not msg.reply_to_message:
        return # Ignore normal photos if not in conversation

    original_text = msg.reply_to_message.text or msg.reply_to_message.caption
    if not original_text or "Ticket:" not in original_text:
        return

    # Extract Ticket ID
    try:
        # Expected: "...Ticket: #TKT-123..." OR "...Ticket ID: #TKT-123..."
        import re
        match = re.search(r"Ticket(?: ID)?:\s*#?(TKT-\d+)", original_text, re.IGNORECASE)
        if not match:
            await msg.reply_text("❌ Could not find Ticket ID in the message you replied to.")
            return

        ticket_id = match.group(1)
        
        # Get Photo from Officer (After Photo)
        photo_file = await msg.photo[-1].get_file()
        after_file_id = photo_file.file_id
        
        from sheets import update_ticket_status, get_ticket_meta
        success = await asyncio.to_thread(update_ticket_status, ticket_id, "Resolved", after_file_id)
        
        if success:
            await msg.reply_text(f"✅ <b>Ticket {ticket_id} Closed!</b>\nStatus updated to Resolved.", parse_mode='HTML')
            
            # --- NOTIFY CITIZEN WITH VISUAL PROOF ---
            meta = await asyncio.to_thread(get_ticket_meta, ticket_id)
            if meta and meta.get("citizen_chat_id"):
                citizen_id = meta["citizen_chat_id"]
                before_file_id = meta.get("photo_file_id")
                
                try:
                    # 1. Send Visual Proof (Before & After)
                    from telegram import InputMediaPhoto
                    media = []
                    if before_file_id:
                        media.append(InputMediaPhoto(media=before_file_id, caption="BEFORE"))
                    media.append(InputMediaPhoto(media=after_file_id, caption="AFTER (Resolved)"))
                    
                    await context.bot.send_media_group(chat_id=citizen_id, media=media)
                    
                    # 2. Ask for Rating
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                    keyboard = [
                        [
                            InlineKeyboardButton("⭐ 1", callback_data=f"rate_{ticket_id}_1"),
                            InlineKeyboardButton("⭐ 2", callback_data=f"rate_{ticket_id}_2"),
                            InlineKeyboardButton("⭐ 3", callback_data=f"rate_{ticket_id}_3"),
                        ],
                        [
                            InlineKeyboardButton("⭐ 4", callback_data=f"rate_{ticket_id}_4"),
                            InlineKeyboardButton("⭐ 5", callback_data=f"rate_{ticket_id}_5"),
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await context.bot.send_message(
                        chat_id=citizen_id,
                        text=f"✅ <b>Ticket #{ticket_id} Resolved!</b>\n\nYour grievance has been attended to.\nPlease rate the resolution quality:",
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logging.error(f"Failed to notify citizen: {e}")

        else:
            await msg.reply_text("❌ Failed to update Sheet.")

    except Exception as e:
        logging.error(f"Reply Handler Error: {e}")
        await msg.reply_text("❌ Error processing resolution.")

async def handle_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles Rating Button Clicks."""
    query = update.callback_query
    await query.answer() # Ack
    
    data = query.data
    # data format: rate_{ticket_id}_{score}
    try:
        _, ticket_id, score = data.split('_')
        
        from sheets import update_ticket_rating
        await asyncio.to_thread(update_ticket_rating, ticket_id, score)
        
        await query.edit_message_text(f"🌟 <b>Thank you for rating us {score} Stars!</b>", parse_mode='HTML')
        
    except Exception as e:
        logging.error(f"Rating Error: {e}")

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
    application.add_handler(CommandHandler("id", cmd_id)) # New ID Command
    application.add_handler(CommandHandler("help", help_command))
    
    # Officer Resolution Handler (Photo Reply) - Must be before ConversationHandler if possible, or added separately
    # Since ConvHandler captures PHOTO, we need to be careful. 
    # Current ConvHandler filters.PHOTO is entry point.
    # If a user is NOT in conversation, this handler should catch it?
    # Actually, ConvHandler has higher priority if added first? No, handlers are checked in order.
    # We want Officer Reply to work independent of "Start Grievance".
    # Strategy: Add Officer Handler BEFORE Conv Handler.
    application.add_handler(MessageHandler(filters.PHOTO & filters.REPLY, handle_officer_reply), group=1)
    
    # Rating Handler
    from telegram.ext import CallbackQueryHandler
    application.add_handler(CallbackQueryHandler(handle_rating_callback, pattern="^rate_"))
    
    application.add_handler(conv_handler)

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
