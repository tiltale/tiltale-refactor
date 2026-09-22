#!/bin/bash
# start_TilTale for macOS: double-click to set up and start TilTale.
# Makes sure Python exists, then hands over to scripts/start_tiltale.py (the visible to-do list).
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
    if command -v brew >/dev/null; then
        echo "Python was not found. Installing it with Homebrew..."
        brew install python
    else
        echo "Python was not found. Install it from https://www.python.org/downloads/ and run this again."
        open "https://www.python.org/downloads/"
        read -r -p "Press Enter to close."
        exit 1
    fi
fi

if [ -f scripts/start_tiltale.py ]; then
    python3 scripts/start_tiltale.py
else
    # Only this launcher is here yet: fetch the to-do app itself, which then downloads the rest.
    python3 -c "import urllib.request; urllib.request.urlretrieve('https://raw.githubusercontent.com/tiltale/tiltale-refactor/main/scripts/start_tiltale.py', 'start_tiltale_tmp.py')"
    python3 start_tiltale_tmp.py
    rm start_tiltale_tmp.py
fi
