import os
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import google.generativeai as genai
from PIL import Image
import io

# --- CONFIGURATION ---
# Replace these with your actual keys or set them as environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8577255418:AAF2h6C0ICMs4IuaweH_5OnSNyWOxYCKQQ4")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCgmROdP8BWwA3ZeHJlZw0jo0R-I-YRWHU")

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest') # Tested & Working

# --- STATES ---
LOCATION = 1

# --- MOCK DATABASE & OFFICERS ---
OFFICER_CONTACTS = {
    "Roads": "Officer_Sharma_Roads",
    "Sanitation": "Officer_Verma_Sanitation",
    "Electricity": "Officer_Singh_Power",
    "Water": "Officer_Gupta_Jal",
    "Other": "General_Admin"
}

# --- BOT FUNCTIONS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
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


async def analyze_image(image_bytes):
    """Sends image to Gemini for analysis."""
    try:
        # Convert bytes to PIL Image
        image = Image.open(io.BytesIO(image_bytes))
        
        prompt = """
        Analyze this image for a public grievance system. 
        1. Identify the main issue. CATEGORIES: [Pothole, Garbage, Streetlight, Water Leakage, Other].
        2. Estimate Severity: [High, Medium, Low].
        3. Provide a 1-sentence description.
        
        Return response in this format:
        Category: <Category>
        Severity: <Severity>
        Description: <Description>
        """
        
        response = model.generate_content([prompt, image])
        return response.text
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return "Error analyzing image. Please try again."

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 1: Analyzes photo and asks for location."""
    status_msg = await update.message.reply_text("🧐 Analyzing your photo with AI... Please wait.")
    
    try:
        # 1. Get the photo file
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # 2. Analyze with Gemini
        analysis_result = await analyze_image(photo_bytes)
        
        # 3. Store analysis in user_data context
        context.user_data['analysis'] = analysis_result
        
        # 4. Ask for Location
        location_keyboard = [[KeyboardButton(text="📍 Share Current Location", request_location=True)]]
        reply_markup = ReplyKeyboardMarkup(location_keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await status_msg.edit_text(
            f"✅ <b>Issue Detected!</b>\n\n{analysis_result}\n\n"
            "📍 <b>Step 2:</b> Please share your **Location** so we can send the officer to the right spot.",
            parse_mode='HTML'
        )
        # Send a separate message with the button because edit_text can't add a new keyboard sometimes
        await update.message.reply_text("Click the button below to share location 👇", reply_markup=reply_markup)
        
        return LOCATION

    except Exception as e:
        logging.error(f"Handler Error: {e}")
        await status_msg.edit_text("❌ Something went wrong while processing the image.")
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
            f"⚠️ <b>Low GPS Accuracy detected ({accuracy:.1f}m).</b>\n"
            "We need precise location (within 20m) for the officer.\n\n"
            "Please wait a few seconds for your GPS to stabilize and <b>Share Location again</b>.",
            parse_mode='HTML'
        )
        # Keep them in the LOCATION state to try again
        return LOCATION

    # Retrieve previous analysis
    analysis_result = context.user_data.get('analysis', 'No Analysis Data')
    
    # Logic to parse category
    category = "Other"
    if "Pothole" in analysis_result: category = "Roads"
    elif "Garbage" in analysis_result: category = "Sanitation"
    elif "Streetlight" in analysis_result: category = "Electricity"
    elif "Water" in analysis_result: category = "Water"
    
    assigned_officer = OFFICER_CONTACTS.get(category, "General_Admin")
    map_link = f"https://www.google.com/maps?q={lat},{lon}"
    
    response_text = (
        f"✅ <b>Ticket Registered Successfully!</b>\n\n"
        f"📂 <b>Category:</b> {category}\n"
        f"👮 <b>Assigned To:</b> {assigned_officer}\n"
        f"📍 <b>Location:</b> <a href='{map_link}'>View on Map</a>\n"
        f"🎯 <b>Accuracy:</b> {accuracy}m\n"
        f"🎫 <b>Ticket ID:</b> #TKT-{update.message.message_id}\n\n"
        f"<i>We have notified the designated officer.</i>"
    )
    
    await update.message.reply_html(response_text, reply_markup=None) # Remove keyboard
    
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
            LOCATION: [MessageHandler(filters.LOCATION, handle_location)],
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
