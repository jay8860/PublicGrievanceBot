#!/bin/bash

# --- SELF HEALING BUILD ---
# If dist folder is missing (due to build phase failure), build it now.
if [ ! -d "dashboard/dist" ]; then
    echo "⚠️ Dashboard Build Missing. Building at Runtime..."
    cd dashboard
    npm install
    npm run build
    cd ..
    echo "✅ Runtime Build Complete."
fi
# --------------------------

# Start the Bot in background
echo "Starting Telegram Bot..."
python bot.py &

# Start the API in foreground (so Railway keeps the container alive based on this port)
echo "Starting Dashboard API..."
uvicorn api:app --host 0.0.0.0 --port $PORT
