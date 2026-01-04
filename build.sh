#!/bin/bash
echo "Installing Python Dependencies..."
pip install -r requirements.txt

echo "Building React Dashboard..."
cd dashboard
npm install
npm run build
cd ..

echo "Build Complete!"
