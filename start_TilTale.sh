#!/bin/sh
# start_TilTale for Linux: run to set up and start TilTale (double-click where the file manager allows it).
# Makes sure Python exists, then hands over to scripts/start_tiltale.py (the visible to-do list).
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null; then
    echo "Python was not found. Installing it (you may be asked for your password)..."
    sudo apt-get install -y python3 python3-venv python3-tk 2>/dev/null || sudo dnf install -y python3 python3-tkinter
fi

if [ -f scripts/start_tiltale.py ]; then
    python3 scripts/start_tiltale.py
else
    # Only this launcher is here yet: fetch the to-do app itself, which then downloads the rest.
    python3 -c "import urllib.request; urllib.request.urlretrieve('https://raw.githubusercontent.com/tiltale/tiltale-refactor/main/scripts/start_tiltale.py', 'start_tiltale_tmp.py')"
    python3 start_tiltale_tmp.py
    rm start_tiltale_tmp.py
fi
