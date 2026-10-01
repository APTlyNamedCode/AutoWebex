# Webex auto-join with Playwright

A small Python/Playwright script that joins a Webex meeting as a guest, ensures the microphone is muted and video is off, then remains in the meeting for a configurable maximum duration.

Tested on Windows and Linux Mint. macOS has not been tested.

## Files

- `join_webex_playwright.py` - main script
- `config.example.json` - example meeting/user configuration
- `requirements.txt` - Python dependency
- `setup_linux_policy.sh` - Linux-only helper for the Chrome for Testing external-protocol policy
- `.gitignore` - keeps your local `config.json` out of Git

## Configuration

Copy the example file:

### Linux

```bash
cp config.example.json config.json
```

### Windows PowerShell

```powershell
Copy-Item config.example.json config.json
```

Edit `config.json`:

```json
{
  "meeting_number": "123 456 789",
  "guest_name": "Example Guest",
  "guest_email": "guest@example.com",
  "meeting_duration_minutes": 120
}
```

`meeting_duration_minutes` is optional and defaults to 120 minutes.

Do not commit `config.json`; it is intentionally listed in `.gitignore`.

## Windows setup

Install Playwright:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Run:

```powershell
python join_webex_playwright.py
```

If you have multiple Python installations, use the same interpreter for installation and execution, for example:

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 -m playwright install chromium
py -3.13 join_webex_playwright.py
```

## Linux Mint setup

These instructions intentionally avoid a Python virtual environment.

Install pip if needed:

```bash
sudo apt update
sudo apt install -y python3-pip
```

Install the Python requirement:

```bash
python3 -m pip install --user --break-system-packages -r requirements.txt
```

Install Playwright's bundled Chromium/Chrome for Testing and its Linux dependencies:

```bash
python3 -m playwright install --with-deps chromium
```

### Linux external-protocol policy

Webex attempts to launch its native `webex://` / `ciscospark://` protocol before falling back to the browser. On Linux, Chrome for Testing may show an `xdg-open` confirmation prompt. That prompt is browser UI rather than page UI and can block unattended automation.

Run the included helper once:

```bash
chmod +x setup_linux_policy.sh
./setup_linux_policy.sh
```

The helper creates:

```text
/etc/opt/chrome_for_testing/policies/managed/webex.json
```

with a URL blocklist for the native Webex protocols. This policy targets Chrome for Testing, which is the browser Playwright installs, rather than the regular system Chromium policy path.

To remove the policy later:

```bash
./setup_linux_policy.sh --remove
```

You can verify the policy by launching Playwright's Chrome for Testing and opening `chrome://policy`. The `URLBlocklist` policy should contain `webex:*` and `ciscospark:*`.

Run the script:

```bash
python3 join_webex_playwright.py
```

## Behaviour

The script:

1. Opens the Webex join page.
2. Enters the configured meeting number.
3. Selects **Join from this browser**.
4. Finds the Webex meeting frame and fills the guest name and email.
5. Waits five seconds for Webex media controls to settle.
6. Mutes the microphone if necessary.
7. Turns video off if necessary.
8. Clicks **Join meeting**.
9. Keeps the browser session open until it is closed or `meeting_duration_minutes` is reached.

## Notes

- The script intentionally runs with a visible browser (`headless=False`).
- The Linux policy helper only configures Chrome for Testing. It does not write to `/etc/chromium/policies/`.
- Scheduling/cron configuration is deliberately not included yet.
- Webex UI changes can require locator updates in the future.
