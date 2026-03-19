#!/bin/bash
set -e

echo "Haram Blocker — Uninstaller"
echo "==========================="
echo ""

echo "Removing application files..."
sudo rm -rf /opt/haram_blocker
sudo rm -f  /usr/local/bin/haram-blocker
sudo rm -f  /usr/share/applications/haram_blocker.desktop
sudo rm -f  /usr/share/pixmaps/haram_blocker.png

for size in 48 64 128 256; do
    sudo rm -f "/usr/share/icons/hicolor/${size}x${size}/apps/haram_blocker.png" 2>/dev/null || true
done
sudo gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
sudo update-desktop-database 2>/dev/null || true

echo "Removing autostart entry..."
rm -f "$HOME/.config/autostart/haram_blocker.desktop"

echo "Cleaning /etc/hosts..."
sudo sed -i '/# === HARAM BLOCKER START ===/,/# === HARAM BLOCKER END ===/d' /etc/hosts

echo "Removing config..."
rm -rf "$HOME/.config/haram_blocker"

echo ""
echo "Uninstall complete."