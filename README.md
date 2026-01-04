# Public Grievance Bot (Demo)

This is a proof-of-concept Telegram bot that uses **Gemini Vision** to identify public grievances (Potholes, Garbage, etc.) from photos and routes them to the correct department.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configuration**:
    *   Open `bot.py`.
    *   Replace `YOUR_TELEGRAM_BOT_TOKEN_HERE` with your token from @BotFather.
    *   Replace `YOUR_GEMINI_API_KEY_HERE` with your Google AI Studio key.

3.  **Run**:
    ```bash
    python bot.py
    ```

## How it Works
1.  User sends a photo.
2.  Bot sends photo to Gemini Pro Vision.
3.  Gemini returns JSON classifiction (Category: Pothole, Severity: High).
4.  Bot "Assigns" it to a predefined officer dictionary.
5.  Bot replies to user with a Ticket ID.
