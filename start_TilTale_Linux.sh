#!/bin/bash
# start_TilTale for Linux: put this file in an empty folder and start it. Ubuntu's Files app opens
# scripts in the text editor on a double-click, so either:
#   - right-click an empty spot in the folder > Open in Terminal, type: bash start_TilTale_Linux.sh
#   - or right-click the file > Properties > turn on "Executable as Program", then right-click > Run as a Program.
#   [1/3] Python:  makes sure Python 3.12 or newer (with tkinter) and Git exist; installs them when
#                  missing with apt or dnf (asks for your password).
#   [2/3] TilTale: downloads TilTale from GitHub into this folder when it is not there yet.
#   [3/3] Window:  opens scripts/start_tiltale.py (the visible to-do list: updates, packages, start).
cd "$(dirname "$0")" || exit 1
ME="$(basename "$0")"

# Started without a terminal ("Run as a Program" in the file manager runs a script invisibly): reopen
# in a terminal window, because this script asks a question and shows its progress.
if [ ! -t 0 ] && [ -z "$TILTALE_IN_TERMINAL" ]; then
    export TILTALE_IN_TERMINAL=1
    SELF="$PWD/$ME"
    if command -v gnome-terminal >/dev/null 2>&1; then exec gnome-terminal -- bash "$SELF"
    elif command -v ptyxis >/dev/null 2>&1; then exec ptyxis -- bash "$SELF"
    elif command -v kgx >/dev/null 2>&1; then exec kgx -- bash "$SELF"
    elif command -v konsole >/dev/null 2>&1; then exec konsole -e bash "$SELF"
    elif command -v xfce4-terminal >/dev/null 2>&1; then exec xfce4-terminal -x bash "$SELF"
    elif command -v mate-terminal >/dev/null 2>&1; then exec mate-terminal -x bash "$SELF"
    elif command -v x-terminal-emulator >/dev/null 2>&1; then exec x-terminal-emulator -e bash "$SELF"
    elif command -v xterm >/dev/null 2>&1; then exec xterm -e bash "$SELF"
    fi
    # No terminal program found: carry on without one (questions are then answered with "no").
fi
printf '\033]0;Starting TilTale\007'

HEAD=$'\033[1;36m'; GOOD=$'\033[32m'; BAD=$'\033[1;31m'; OFF=$'\033[0m'

# One log for the whole start, from the very first line: start_TilTale.log next to this file.
# start_tiltale.py adds to it (TILTALE_LOG_STARTED tells it not to empty it).
LOG="$PWD/start_TilTale.log"
export TILTALE_LOG_STARTED=1
{ echo "$(date)  $ME started"; echo "Folder: $PWD"; cat /etc/os-release 2>/dev/null | head -2; } >"$LOG"

say()  { printf '    %s\n' "$1"; printf '%s  %s\n' "$(date +%H:%M:%S)" "$1" >>"$LOG"; }
step() { printf '\n%s[%s/3] %s%s\n' "$HEAD" "$1" "$2" "$OFF"; echo "=== [$1/3] $2" >>"$LOG"; }
done_() { printf '    %sDone.%s\n' "$GOOD" "$OFF"; }
failed() {  # $1 = code, $2 = message: keep the window open and show the log
    echo "$(date)  stopped with code $1" >>"$LOG"
    printf '\n%s%s%s\nThe log opens now: %s\n' "$BAD" "$2" "$OFF" "$LOG"
    xdg-open "$LOG" >/dev/null 2>&1
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
            "$ME"|start_TilTale*|start_tiltale_tmp.py|"*"|".[!.]*") ;;
            *) OTHER="$item" ;;
        esac
    done
    if [ -n "$OTHER" ]; then
        TRACES=
        for t in studio frame-types components runtime/tiltale.js branding/logo-tiltale.png project/project.sqlite3; do
            [ -e "$t" ] && TRACES=1
        done
        for f in .git/config README.md config/settings.py; do
            [ -f "$f" ] && grep -qi tiltale "$f" && TRACES=1
        done
        if [ -z "$TRACES" ]; then
            echo "Folder is not empty, it contains for example: $OTHER" >>"$LOG"
            printf '%sThis folder already contains other files.%s\nPut %s in a new, empty folder and run it there.\n' "$BAD" "$OFF" "$ME"
            failed 4 "Starting TilTale did not work (code 4)."
        fi
        echo "Damaged TilTale folder: scripts/start_tiltale.py is missing." >>"$LOG"
        FIRST=; DAMAGED=1
        printf '%sSome of TilTale'"'"'s own files are missing in this folder.%s\n' "$BAD" "$OFF"
        echo "The TilTale window will open and offer to repair it. Your project is not touched."
        echo
    fi
fi

# ==================================================================== find Python and Git
CHECK='import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 12) else 1)'
PY=; PYVERSION=; OLDPY=
trypython() {
    command -v "$1" >/dev/null 2>&1 || return
    "$1" -c "$CHECK" >>"$LOG" 2>&1 && { PY="$1"; PYVERSION="$("$1" -c 'import platform; print(platform.python_version())')"; return; }
    [ -z "$OLDPY" ] && OLDPY="$("$1" -c 'import platform; print(platform.python_version())' 2>/dev/null)"
}
findpython() { for p in python3 python3.14 python3.13 python3.12; do trypython "$p"; [ -n "$PY" ] && return; done; }
findpython
echo "Python: $PY $PYVERSION / older Python: $OLDPY" >>"$LOG"
HAVE_GIT=; command -v git >/dev/null 2>&1 && HAVE_GIT=1
# The package manager of this Linux, and what to install with it.
if command -v apt-get >/dev/null 2>&1; then
    INSTALL="sudo apt-get install -y"; PKGS="python3 python3-venv python3-tk git"
elif command -v dnf >/dev/null 2>&1; then
    INSTALL="sudo dnf install -y"; PKGS="python3 python3-tkinter git"
elif command -v pacman >/dev/null 2>&1; then
    INSTALL="sudo pacman -S --noconfirm"; PKGS="python tk git"
else
    INSTALL=; PKGS=
fi

# ==================================================================== welcome
if [ -n "$FIRST" ]; then
    SPACE=160; [ -z "$PY" ] && SPACE=$((SPACE + 100)); [ -z "$HAVE_GIT" ] && SPACE=$((SPACE + 50))
    printf '\n%sWelcome to TilTale!%s\n\n' "$HEAD" "$OFF"
    echo "TilTale will be set up in this folder:"
    echo "    $PWD"
    echo
    echo "What will happen:"
    if [ -n "$PY" ] && [ -n "$HAVE_GIT" ]; then
        echo "  1. Python   Python $PYVERSION and Git are already on this computer: nothing to install."
    else
        echo "  1. Python   Python 3.12 or newer (with tkinter) and Git are installed with: $INSTALL ..."
        echo "              This asks for your password."
        [ -n "$OLDPY" ] && echo "              (This computer has Python $OLDPY, but TilTale needs 3.12 or newer.)"
    fi
    echo "  2. TilTale  Downloaded from GitHub into this folder."
    echo "  3. Setup    A small window installs TilTale's packages, about 150 MB."
    echo "              Then TilTale opens in your browser."
    echo
    echo "Disk space needed: about $SPACE MB. The first start takes about 5 to 15 minutes."
    echo
    read -r -p "Continue? Type Y for yes or N for no: " ANSWER
    case "$ANSWER" in
        [Yy]*) echo "User chose to continue." >>"$LOG" ;;
        *) echo "User chose not to continue." >>"$LOG"; echo; echo "Nothing was changed. You can close this window."; exit 0 ;;
    esac
fi

# ==================================================================== [1/3] Python and Git
[ -n "$FIRST" ] && step 1 "Python and Git"
if [ -z "$PY" ] || [ -z "$HAVE_GIT" ]; then
    [ -z "$INSTALL" ] && failed 1 "Python 3.12 or newer (with tkinter) and Git are needed. Install them with your package manager, then run $ME again."
    say "Installing with: $INSTALL $PKGS (your password may be asked)"
    echo "--- $INSTALL $PKGS" >>"$LOG"
    # shellcheck disable=SC2086
    $INSTALL $PKGS 2>&1 | tee -a "$LOG" | grep -iE "error|unable|not found" | head -5
    findpython
    command -v git >/dev/null 2>&1 && HAVE_GIT=1
    if [ -z "$PY" ]; then
        if [ -n "$OLDPY" ]; then
            failed 1 "This Linux comes with Python $OLDPY, but TilTale needs 3.12 or newer with tkinter. Install a newer Python (for example from https://www.python.org/downloads/ or the deadsnakes PPA), then run $ME again."
        fi
        failed 1 "Python 3.12 or newer with tkinter could not be installed. Install it with your package manager, then run $ME again."
    fi
    [ -n "$HAVE_GIT" ] || failed 1 "Git could not be installed. Install it with your package manager, then run $ME again."
elif [ -n "$FIRST" ]; then
    say "Python $PYVERSION and Git are already on this computer."
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
    if command -v curl >/dev/null 2>&1; then
        curl -fL -# -o tiltale.zip "$URL" || rm -f tiltale.zip
    else
        wget -q --show-progress -O tiltale.zip "$URL" || rm -f tiltale.zip
    fi
    [ -f tiltale.zip ] || failed 3 "TilTale could not be downloaded. Check the internet connection and try again."
    say "Unpacking TilTale..."
    "$PY" -m zipfile -e tiltale.zip _tiltale_download >>"$LOG" 2>&1
    INNER="$(ls -d _tiltale_download/*/ 2>/dev/null | head -1)"
    if [ -n "$DAMAGED" ]; then
        mkdir -p scripts branding
        cp "$INNER/scripts/start_tiltale.py" scripts/
        for b in launcher-logo.png launcher-logo@2x.png favicon.ico logo.png; do
            [ -e "branding/$b" ] || cp "$INNER/branding/$b" branding/ 2>/dev/null
        done
    else
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
    echo "can open TilTale in your browser. Next time, just run $ME again."
elif [ -n "$DAMAGED" ]; then
    echo "Click Start in that window: it shows what is missing and offers Repair."
else
    echo "Click Start in that window to open TilTale in your browser."
fi
echo
echo "This terminal window closes in 10 seconds."
sleep 10
exit 0
