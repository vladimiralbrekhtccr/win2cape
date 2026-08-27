#!/bin/sh
# Installs a .cape so it re-applies at every login.
#
#   ./install.sh /path/to/MyTheme.cape [scale]
#
# Needs no root, no admin password, and installs no privileged daemon - just a
# per-user LaunchAgent you own and can delete.
set -e

CAPE="$1"
SCALE="${2:-1.0}"
DIR="$HOME/Library/Application Support/CursorCape"
LABEL="com.win2cape.cursor"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

[ -n "$CAPE" ] && [ -f "$CAPE" ] || { echo "usage: ./install.sh /path/to/Theme.cape [scale]"; exit 1; }

# mousecloak ships inside Mousecape.app. Locate it, or take it from ./mousecloak.
MC=""
for c in "$DIR/mousecloak" \
         "/Applications/Mousecape.app/Contents/MacOS/mousecloak" \
         "$HOME/Applications/Mousecape.app/Contents/MacOS/mousecloak" \
         "$(dirname "$0")/mousecloak"; do
    [ -x "$c" ] && MC="$c" && break
done
[ -n "$MC" ] || {
    echo "Could not find 'mousecloak'."
    echo "Download Mousecape, then copy Mousecape.app/Contents/MacOS/mousecloak next to this script."
    exit 1
}

mkdir -p "$DIR" "$HOME/Library/LaunchAgents"
[ "$MC" = "$DIR/mousecloak" ] || cp "$MC" "$DIR/mousecloak"
chmod +x "$DIR/mousecloak"
cp "$CAPE" "$DIR/theme.cape"

echo "Backing up your current cursors..."
"$DIR/mousecloak" --dump "$DIR/original-cursors-backup.cape" >/dev/null 2>&1 || true

cat > "$DIR/apply-cursor.sh" <<INNER
#!/bin/sh
# Re-applies the cape at login. Cursor registration only sticks once the GUI
# session is up, so apply a few times with backoff rather than once immediately.
DIR="\$HOME/Library/Application Support/CursorCape"
SCALE=$SCALE
[ -x "\$DIR/mousecloak" ] || exit 1
for delay in 5 10 20; do
    sleep "\$delay"
    "\$DIR/mousecloak" --apply "\$DIR/theme.cape" >/dev/null 2>&1
done
# Cursor scale is a per-session setting, so it must be re-set at each login.
"\$DIR/mousecloak" --scale "\$SCALE" >/dev/null 2>&1
echo "\$(date '+%Y-%m-%d %H:%M:%S') applied cape at scale \$SCALE" >> "\$DIR/apply.log"
INNER
chmod +x "$DIR/apply-cursor.sh"

cat > "$PLIST" <<INNER
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>$DIR/apply-cursor.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>$DIR/stderr.log</string>
</dict>
</plist>
INNER

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "Applying now..."
"$DIR/mousecloak" --apply "$DIR/theme.cape" >/dev/null 2>&1
[ "$SCALE" = "1.0" ] || "$DIR/mousecloak" --scale "$SCALE" >/dev/null 2>&1

echo "Done. Installed to $DIR"
echo "Uninstall with: ./uninstall.sh"
