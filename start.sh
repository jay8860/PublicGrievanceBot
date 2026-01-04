#!/bin/bash

# Start the Bot in background
echo "Starting Telegram Bot..."
python bot.py &

# Start the API in foreground (so Railway keeps the container alive based on this port)
echo "Starting Dashboard API..."
uvicorn api:app --host 0.0.0.0 --port $PORT
