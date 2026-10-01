#!/usr/bin/env bash
set -euo pipefail

POLICY_DIR="/etc/opt/chrome_for_testing/policies/managed"
POLICY_FILE="$POLICY_DIR/webex.json"

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "This helper is for Linux only." >&2
    exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
    exec sudo "$0" "$@"
fi

if [[ "${1:-}" == "--remove" ]]; then
    rm -f "$POLICY_FILE"
    echo "Removed: $POLICY_FILE"
    exit 0
fi

install -d -m 0755 "$POLICY_DIR"

cat > "$POLICY_FILE" <<'EOF'
{
  "URLBlocklist": [
    "webex:*",
    "ciscospark:*"
  ]
}
EOF

chmod 0644 "$POLICY_FILE"

echo "Installed Chrome for Testing policy: $POLICY_FILE"
echo "This policy blocks native Webex protocol launches so the browser join flow can run unattended."
echo "To remove it later, run: $0 --remove"
