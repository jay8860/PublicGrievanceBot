import os
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from PIL import Image
import io

# --- CONFIGURATION ---
# Replace these with your actual keys or set them as environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8577255418:AAF2h6C0ICMs4IuaweH_5OnSNyWOxYCKQQ4")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCu-e_StxwnqKr5znXoL5FkFldxhTNXORU")

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash') # Logic: Fast and good at vision

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

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Downloads photo, sends to AI, and routes traffic."""
    status_msg = await update.message.reply_text("🧐 Analyzing your photo with AI... Please wait.")
    
    try:
        # 1. Get the photo file
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # 2. Analyze with Gemini
        analysis_result = await analyze_image(photo_bytes)
        
        # 3. Parse Result (Simple parsing for demo)
        category = "Other"
        if "Pothole" in analysis_result: category = "Roads"
        elif "Garbage" in analysis_result: category = "Sanitation"
        elif "Streetlight" in analysis_result: category = "Electricity"
        elif "Water" in analysis_result: category = "Water"
        
        assigned_officer = OFFICER_CONTACTS.get(category, "General_Admin")
        
        # 4. Reply to Citizen
        response_text = (
            f"✅ <b>Analysis Complete</b>\n\n"
            f"{analysis_result}\n\n"
            f"--------------------------------\n"
            f"📂 <b>Category:</b> {category}\n"
            f"👮 <b>Assigned To:</b> {assigned_officer}\n"
            f"🎫 <b>Ticket Created:</b> #TKT-{update.message.message_id}\n"
        )
        
        await status_msg.edit_text(response_text, parse_mode='HTML')
        
        # 5. (Optional) Simulate forwarding to Officer
        # In a real app, we would send a message to the Officer's Chat ID here.
        # await context.bot.send_message(chat_id=OFFICER_CHAT_ID, text=f"New Grievance assigned: {analysis_result}")

    except Exception as e:
        logging.error(f"Handler Error: {e}")
        await status_msg.edit_text("❌ Something went wrong while processing the image.")

# --- MAIN ---

def main() -> None:
    """Start the bot."""
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("ERROR: Please update the TELEGRAM_BOT_TOKEN in the script.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Handle photos
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
