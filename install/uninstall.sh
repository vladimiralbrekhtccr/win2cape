#!/bin/sh
# Removes the cursor setup completely and restores the macOS defaults.
DIR="$HOME/Library/Application Support/CursorCape"
LABEL="com.win2cape.cursor"

echo "Unloading login agent..."
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"

echo "Restoring default macOS cursors..."
[ -x "$DIR/mousecloak" ] && "$DIR/mousecloak" --scale 1.0 >/dev/null 2>&1
[ -x "$DIR/mousecloak" ] && "$DIR/mousecloak" --reset

echo "Removing files..."
rm -rf "$DIR"
echo "Done. If anything still looks off, log out and back in."
