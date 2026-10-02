#!/bin/bash
# start_TilTale for macOS: put this file in an empty folder and double-click it.
#   [1/3] Python:  makes sure Python 3.12 or newer (with tkinter) exists; installs it when missing.
#   [2/3] TilTale: downloads TilTale from GitHub into this folder when it is not there yet.
#   [3/3] Window:  opens scripts/start_tiltale.py (the visible to-do list: Git, updates, packages,
#                  start), waits until its window is open, and then closes this Terminal window.
# First time macOS refuses to open it ("unidentified developer"): right-click it and choose Open.
cd "$(dirname "$0")" || exit 1
ME="$(basename "$0")"
printf '\033]0;Starting TilTale\007'  # the Terminal window's title

HEAD=$'\033[1;36m'; GOOD=$'\033[32m'; BAD=$'\033[1;31m'; OFF=$'\033[0m'

# One log for the whole start, from the very first line: start_TilTale.log next to this file.
# start_tiltale.py adds to it (TILTALE_LOG_STARTED tells it not to empty it).
LOG="$PWD/start_TilTale.log"
export TILTALE_LOG_STARTED=1
{ echo "$(date)  $ME started"; echo "Folder: $PWD"; sw_vers 2>/dev/null; } >"$LOG"

say()  { printf '    %s\n' "$1"; printf '%s  %s\n' "$(date +%H:%M:%S)" "$1" >>"$LOG"; }
step() { printf '\n%s[%s/3] %s%s\n' "$HEAD" "$1" "$2" "$OFF"; echo "=== [$1/3] $2" >>"$LOG"; }
done_() { printf '    %sDone.%s\n' "$GOOD" "$OFF"; }
failed() {  # $1 = code, $2 = message: keep the window open and show the log
    echo "$(date)  stopped with code $1" >>"$LOG"
    printf '\n%s%s%s\nThe log opens now: %s\n' "$BAD" "$2" "$OFF" "$LOG"
    open -e "$LOG" 2>/dev/null
    read -r -p "Press Enter to close this window. "
    exit "$1"
}

# ==================================================================== what is here already?
FIRST=1; DAMAGED=
[ -f scripts/start_tiltale.py ] && FIRST=
if [ -n "$FIRST" ]; then
    rm -rf _tiltale_download tiltale.zip
    OTHER=
    for item in * .[!.]*; do
        case "$item" in
            "$ME"|start_TilTale*|start_tiltale_tmp.py|.DS_Store|"*"|".[!.]*") ;;
            *) OTHER="$item" ;;
        esac
    done
    if [ -n "$OTHER" ]; then
        # Not empty: a TilTale folder with files deleted? Only things a TilTale folder has count.
        TRACES=
        for t in studio frame-types components runtime/tiltale.js branding/logo-tiltale.png project/project.sqlite3; do
            [ -e "$t" ] && TRACES=1
        done
        for f in .git/config README.md config/settings.py; do
            [ -f "$f" ] && grep -qi tiltale "$f" && TRACES=1
        done
        if [ -z "$TRACES" ]; then
            echo "Folder is not empty, it contains for example: $OTHER" >>"$LOG"
            printf '%sThis folder already contains other files.%s\nPut %s in a new, empty folder and double-click it there.\n' "$BAD" "$OFF" "$ME"
            failed 4 "Starting TilTale did not work (code 4)."
        fi
        echo "Damaged TilTale folder: scripts/start_tiltale.py is missing." >>"$LOG"
        FIRST=; DAMAGED=1
        printf '%sSome of TilTale'"'"'s own files are missing in this folder.%s\n' "$BAD" "$OFF"
        echo "The TilTale window will open and offer to repair it. Your project is not touched."
        echo
    fi
fi

# ==================================================================== find Python
# TilTale needs Python 3.12 or newer with tkinter. The python3 that comes with macOS is older and
# only works after Apple's command line tools are installed, so it does not count.
CHECK='import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 12) else 1)'
PY=; PYVERSION=; OLDPY=
trypython() {  # $1 = a python to try
    [ -x "$1" ] || return
    "$1" -c "$CHECK" >>"$LOG" 2>&1 && { PY="$1"; PYVERSION="$("$1" -c 'import platform; print(platform.python_version())')"; return; }
    [ -z "$OLDPY" ] && OLDPY="$("$1" -c 'import platform; print(platform.python_version())' 2>/dev/null)"
}
findpython() {
    for v in 3.14 3.13 3.12; do trypython "/Library/Frameworks/Python.framework/Versions/$v/bin/python3"; [ -n "$PY" ] && return; done
    for p in /opt/homebrew/bin/python3 /usr/local/bin/python3; do trypython "$p"; [ -n "$PY" ] && return; done
}
findpython
echo "Python: $PY $PYVERSION / older Python: $OLDPY" >>"$LOG"
HAVE_GIT=; xcode-select -p >/dev/null 2>&1 && HAVE_GIT=1

# ==================================================================== welcome
if [ -n "$FIRST" ]; then
    SPACE=160; [ -z "$PY" ] && SPACE=$((SPACE + 150)); [ -z "$HAVE_GIT" ] && SPACE=$((SPACE + 1500))
    printf '\n%sWelcome to TilTale!%s\n\n' "$HEAD" "$OFF"
    echo "TilTale will be set up in this folder:"
    echo "    $PWD"
    echo
    echo "What will happen:"
    if [ -n "$PY" ]; then
        echo "  1. Python   Python $PYVERSION is already on this Mac: nothing to install."
    elif [ -n "$OLDPY" ]; then
        echo "  1. Python   This Mac has Python $OLDPY, but TilTale needs 3.12 or newer."
        echo "              Python 3.12 is added next to it, about 150 MB. Python $OLDPY stays as it is."
    else
        echo "  1. Python   Not on this Mac yet: Python 3.12 will be installed, about 150 MB."
    fi
    echo "  2. TilTale  Downloaded from GitHub into this folder."
    if [ -n "$HAVE_GIT" ]; then
        echo "  3. Setup    A small window installs TilTale's packages, about 150 MB."
    else
        echo "  3. Setup    A small window installs Apple's command line tools (for Git), about 1.5 GB,"
        echo "              and TilTale's packages, about 150 MB."
    fi
    echo "              Then TilTale opens in your browser."
    echo
    echo "Disk space needed: about $SPACE MB. The first start takes about 5 to 20 minutes."
    echo
    read -r -p "Continue? Type Y for yes or N for no: " ANSWER
    case "$ANSWER" in
        [Yy]*) echo "User chose to continue." >>"$LOG" ;;
        *) echo "User chose not to continue." >>"$LOG"; echo; echo "Nothing was changed. You can close this window."; exit 0 ;;
    esac
fi

# ==================================================================== [1/3] Python
[ -n "$FIRST" ] && step 1 "Python"
if [ -z "$PY" ]; then
    [ -z "$FIRST" ] && say "TilTale needs Python 3.12 or newer. Installing it now..."
    PYVER=3.12.10
    PKG="$TMPDIR/python-$PYVER-macos11.pkg"
    say "Downloading Python $PYVER, about 45 MB..."
    echo "--- download https://www.python.org/ftp/python/$PYVER/python-$PYVER-macos11.pkg" >>"$LOG"
    if curl -fL -# -o "$PKG" "https://www.python.org/ftp/python/$PYVER/python-$PYVER-macos11.pkg"; then
        say "The Python installer opens now. Click Continue, Agree and Install; then come back here."
        open -W "$PKG"  # -W: wait until the installer is closed
        rm -f "$PKG"
        findpython
    else
        say "The download failed."
    fi
    if [ -z "$PY" ]; then
        printf '%sPython could not be installed.%s\nInstall it from https://www.python.org/downloads/macos/ and double-click %s again.\n' "$BAD" "$OFF" "$ME"
        open https://www.python.org/downloads/macos/
        failed 1 "Starting TilTale did not work (code 1)."
    fi
elif [ -n "$FIRST" ]; then
    say "Python $PYVERSION is already on this Mac."
fi
echo "Using Python: $PY" >>"$LOG"
"$PY" --version >>"$LOG" 2>&1
[ -n "$FIRST" ] && done_

# ==================================================================== [2/3] TilTale
if [ -n "$FIRST" ] || [ -n "$DAMAGED" ]; then
    [ -n "$FIRST" ] && step 2 "TilTale"
    URL="https://github.com/tiltale/tiltale-refactor/archive/refs/heads/main.zip"
    say "Downloading TilTale from GitHub..."
    echo "--- download $URL" >>"$LOG"
    curl -fL -# -o tiltale.zip "$URL" || rm -f tiltale.zip
    [ -f tiltale.zip ] || failed 3 "TilTale could not be downloaded. Check the internet connection and try again."
    say "Unpacking TilTale..."
    "$PY" -m zipfile -e tiltale.zip _tiltale_download >>"$LOG" 2>&1
    INNER="$(ls -d _tiltale_download/*/ 2>/dev/null | head -1)"
    if [ -n "$DAMAGED" ]; then
        # Damaged folder: put back only the TilTale window (and its pictures when missing). Nothing
        # else is changed here; the window's Repair button puts back the rest, after asking.
        mkdir -p scripts branding
        cp "$INNER/scripts/start_tiltale.py" scripts/
        for b in launcher-logo.png launcher-logo@2x.png favicon.ico logo.png; do
            [ -e "branding/$b" ] || cp "$INNER/branding/$b" branding/ 2>/dev/null
        done
    else
        # The ZIP holds one folder: move its contents here, next to this file. Nothing that already
        # exists is replaced (above all not this launcher).
        for item in "$INNER"* "$INNER".[!.]*; do
            name="$(basename "$item")"
            [ -e "$item" ] && [ ! -e "$name" ] && mv "$item" .
        done
    fi
    rm -rf _tiltale_download tiltale.zip
    [ -f scripts/start_tiltale.py ] || failed 5 "TilTale was downloaded but could not be unpacked."
    [ -n "$FIRST" ] && done_
fi

# ==================================================================== [3/3] the TilTale window
if [ -n "$FIRST" ]; then step 3 "TilTale window"; else printf '%sStarting TilTale...%s\n' "$HEAD" "$OFF"; fi
echo "--- start $PY scripts/start_tiltale.py" >>"$LOG"
# Started in its own session, so it keeps running after this Terminal window closes.
"$PY" -c "import subprocess, sys; subprocess.Popen([sys.executable, 'scripts/start_tiltale.py'], start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)"
say "Opening the TilTale window..."
WAITED=0
while ! grep -q "Window open" "$LOG"; do
    grep -q "Crashed:" "$LOG" && failed 6 "The TilTale window did not open."
    [ "$WAITED" -ge 30 ] && failed 6 "The TilTale window did not open."
    sleep 1; WAITED=$((WAITED + 1))
done
[ -n "$FIRST" ] && done_
printf '\n%sAll set: the "Start TilTale" window is open.%s\n' "$GOOD" "$OFF"
if [ -n "$FIRST" ]; then
    echo "Click Start in that window. It installs what TilTale still needs, and then you"
    echo "can open TilTale in your browser. Next time, just double-click $ME again."
elif [ -n "$DAMAGED" ]; then
    echo "Click Start in that window: it shows what is missing and offers Repair."
else
    echo "Click Start in that window to open TilTale in your browser."
fi
echo
echo "This Terminal window closes in 5 seconds."
sleep 5
osascript -e 'tell application "Terminal" to close (every window whose name contains "TilTale")' >/dev/null 2>&1 &
exit 0
