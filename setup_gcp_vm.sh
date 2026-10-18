#!/usr/bin/env bash
# ==============================================================================
# Google Cloud VM Automated Setup Script for Singapore Pools TOTO Bot
# Tested on Ubuntu 22.04 / 24.04 LTS on GCP e2-micro
# ==============================================================================

set -e

echo "=========================================================="
echo "🚀 Setting up TOTO Auto-Buyer on Google Cloud VM..."
echo "=========================================================="

# 1. Update packages
echo "📦 Updating system packages..."
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv git curl

# 2. Setup 2GB Swap Memory (Crucial for e2-micro 1GB RAM)
if [ ! -f /swapfile ]; then
    echo "💾 Creating 2GB swap file to prevent out-of-memory errors..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "✅ Swap memory enabled."
else
    echo "✅ Swap file already exists."
fi

# 3. Create Python Virtual Environment
echo "🐍 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# 4. Install Python requirements
echo "📚 Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Install Playwright Chromium & OS system dependencies
echo "🌐 Installing Playwright Chromium browser & system dependencies..."
playwright install --with-deps chromium

# 6. Setup systemd service for 24/7 background operation
echo "⚙️ Configuring systemd service..."
CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)

cat <<EOF | sudo tee /etc/systemd/system/totobot.service
[Unit]
Description=Singapore Pools TOTO Auto-Buyer Telegram Bot
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${CURRENT_DIR}
ExecStart=${CURRENT_DIR}/venv/bin/python bot.py
Restart=always
RestartSec=10
EnvironmentFile=${CURRENT_DIR}/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable totobot

echo ""
echo "=========================================================="
echo "🎉 Setup complete!"
echo "=========================================================="
echo "Next steps:"
echo "1. Create your .env file:  nano .env"
echo "2. Start the service:      sudo systemctl start totobot"
echo "3. Check logs:             sudo journalctl -u totobot -f"
echo "=========================================================="
