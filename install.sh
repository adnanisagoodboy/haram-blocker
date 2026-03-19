#!/bin/bash
set -e

INSTALL_DIR="/opt/haram_blocker"
BIN="/usr/local/bin/haram-blocker"
DESKTOP="/usr/share/applications/haram_blocker.desktop"
ICON_DIR="/usr/share/icons/hicolor"

echo ""
echo "Haram Blocker v1.0 — Installer"
echo "================================"
echo ""

command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found."; exit 1; }
python3 -c "import tkinter" 2>/dev/null || {
    echo "Installing python3-tk..."
    sudo apt-get install -y python3-tk
}

echo "Copying files..."
sudo mkdir -p "$INSTALL_DIR/data" "$INSTALL_DIR/assets"
sudo cp haram_blocker.py  "$INSTALL_DIR/"
sudo cp data/domains.csv  "$INSTALL_DIR/data/"
sudo cp assets/icon.svg   "$INSTALL_DIR/assets/"
[ -f assets/icon.png ] && sudo cp assets/icon.png "$INSTALL_DIR/assets/"
sudo chmod +x "$INSTALL_DIR/haram_blocker.py"

echo "Installing icon..."
if [ -f assets/icon.png ]; then
    sudo cp assets/icon.png "/usr/share/pixmaps/haram_blocker.png"
    for size in 48 64 128 256; do
        sudo mkdir -p "$ICON_DIR/${size}x${size}/apps"
        sudo cp assets/icon.png "$ICON_DIR/${size}x${size}/apps/haram_blocker.png" 2>/dev/null || true
    done
    sudo gtk-update-icon-cache "$ICON_DIR" 2>/dev/null || true
fi

echo "Creating launcher..."
sudo bash -c "cat > $BIN << 'EOF'
#!/bin/bash
python3 /opt/haram_blocker/haram_blocker.py "\$@"
EOF"
sudo chmod +x "$BIN"

echo "Creating desktop entry..."
sudo bash -c "cat > $DESKTOP << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Haram Blocker
GenericName=Content Blocker
Comment=Block adult, gambling, dating and drug websites system-wide
Exec=python3 /opt/haram_blocker/haram_blocker.py
Icon=haram_blocker
Terminal=false
StartupNotify=true
Categories=System;Security;Utility;
Keywords=block;haram;parental;filter;adult;gambling;
EOF"
sudo update-desktop-database 2>/dev/null || true

echo ""
echo "Installation complete."
echo ""
echo "  Launch: App menu -> Haram Blocker"
echo "  Or:     haram-blocker"
echo ""
echo "  Default password: bismillah"
echo "  Change it in the app after first launch."
echo ""