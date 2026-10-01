import json
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import (
    sync_playwright,
    expect,
    Error as PlaywrightError,
)


CONFIG_PATH = Path(__file__).resolve().with_name("config.json")
MEDIA_SETTLE_SECONDS = 5


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def load_config():
    if not CONFIG_PATH.exists():
        raise RuntimeError(
            f"Missing {CONFIG_PATH.name}. Copy config.example.json to "
            f"{CONFIG_PATH.name} and edit it first."
        )

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = json.load(file)

    required = ("meeting_number", "guest_name", "guest_email")
    missing = [key for key in required if not str(config.get(key, "")).strip()]

    if missing:
        raise RuntimeError(
            "Missing required config value(s): " + ", ".join(missing)
        )

    duration_minutes = config.get("meeting_duration_minutes", 120)

    try:
        duration_minutes = int(duration_minutes)
    except (TypeError, ValueError) as error:
        raise RuntimeError("meeting_duration_minutes must be an integer.") from error

    if duration_minutes <= 0:
        raise RuntimeError("meeting_duration_minutes must be greater than zero.")

    return {
        "meeting_number": str(config["meeting_number"]).strip(),
        "guest_name": str(config["guest_name"]).strip(),
        "guest_email": str(config["guest_email"]).strip(),
        "meeting_duration_seconds": duration_minutes * 60,
    }


def find_webex_form(page, timeout_seconds=30):
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        for frame in page.frames:
            try:
                textboxes = frame.get_by_role("textbox")
                visible = []

                for i in range(textboxes.count()):
                    textbox = textboxes.nth(i)
                    if textbox.is_visible():
                        visible.append(textbox)

                if len(visible) >= 2:
                    log(f"Found Webex form frame: {frame.url}")
                    return frame, visible[0], visible[1]

            except PlaywrightError:
                pass

        time.sleep(0.5)

    raise RuntimeError("Could not find the Webex Name and Email fields.")


def ensure_microphone_muted(frame):
    microphone = frame.locator(
        "mdc-button[data-test='microphone-button']"
    )

    expect(microphone).to_be_visible(timeout=15_000)
    expect(microphone).to_have_attribute(
        "aria-label",
        re.compile(
            r"microphone is currently (muted|unmuted)",
            re.IGNORECASE,
        ),
        timeout=20_000,
    )

    label = (microphone.get_attribute("aria-label") or "").casefold()
    log(f"Microphone status: {label!r}")

    if "microphone is currently muted" in label:
        log("Microphone is already muted.")
        return

    if "microphone is currently unmuted" in label:
        microphone.click()
        expect(microphone).to_have_attribute(
            "aria-label",
            re.compile(
                r"microphone is currently muted",
                re.IGNORECASE,
            ),
            timeout=10_000,
        )
        log("Microphone muted.")
        return

    raise RuntimeError(f"Unrecognised microphone status: {label!r}")


def ensure_video_off(frame):
    camera = frame.locator(
        "mdc-button[data-test='camera-button']"
    )

    expect(camera).to_be_visible(timeout=15_000)
    expect(camera).to_have_attribute(
        "aria-label",
        re.compile(
            r"sending video is currently (enabled|disabled)",
            re.IGNORECASE,
        ),
        timeout=20_000,
    )

    label = (camera.get_attribute("aria-label") or "").casefold()
    log(f"Camera status: {label!r}")

    if "sending video is currently disabled" in label:
        log("Video is already off.")
        return

    if "sending video is currently enabled" in label:
        camera.click()
        expect(camera).to_have_attribute(
            "aria-label",
            re.compile(
                r"sending video is currently disabled",
                re.IGNORECASE,
            ),
            timeout=10_000,
        )
        log("Video turned off.")
        return

    raise RuntimeError(f"Unrecognised camera status: {label!r}")


def wait_until_browser_closes(browser, page, maximum_seconds):
    deadline = time.monotonic() + maximum_seconds

    while time.monotonic() < deadline:
        try:
            if not browser.is_connected():
                log("Automated browser session ended.")
                return

            if page.is_closed():
                log("Automated browser window was closed.")
                return

            page.wait_for_timeout(1000)

        except PlaywrightError:
            log("Automated browser session ended.")
            return

    log("Maximum meeting duration reached.")


def join_webex_meeting():
    config = load_config()

    with sync_playwright() as playwright:
        browser = None

        try:
            browser = playwright.chromium.launch(headless=False)

            context = browser.new_context(
                viewport={
                    "width": 1920,
                    "height": 1080,
                },
                permissions=[
                    "microphone",
                    "camera",
                ],
                locale="en-GB",
            )

            context.set_default_timeout(30_000)
            page = context.new_page()

            log("Opening the Webex join page.")
            page.goto(
                "https://signin.webex.com/join",
                wait_until="domcontentloaded",
            )

            meeting_input = page.locator("input.el-input__inner")
            meeting_input.fill(config["meeting_number"])
            meeting_input.press("Enter")
            log("Meeting number submitted.")

            join_browser = page.locator("#broadcom-center-right")
            expect(join_browser).to_be_visible(timeout=30_000)
            join_browser.click()
            log("Clicked 'Join from this browser'.")

            frame, name_input, email_input = find_webex_form(page)

            name_input.fill(config["guest_name"])
            expect(name_input).to_have_value(config["guest_name"])
            log("Name entered.")

            email_input.fill(config["guest_email"])
            expect(email_input).to_have_value(config["guest_email"])
            log("Email entered.")

            log(
                f"Waiting {MEDIA_SETTLE_SECONDS} seconds "
                "for microphone and camera controls to settle."
            )
            page.wait_for_timeout(MEDIA_SETTLE_SECONDS * 1000)

            ensure_microphone_muted(frame)
            ensure_video_off(frame)

            join_button = frame.get_by_role(
                "button",
                name=re.compile(r"join meeting", re.IGNORECASE),
            )
            expect(join_button).to_be_visible(timeout=15_000)
            expect(join_button).to_be_enabled(timeout=15_000)
            join_button.click()

            log("Join meeting clicked.")
            log(
                "Join sequence completed. Browser will remain open for up to "
                f"{config['meeting_duration_seconds'] // 60} minutes."
            )

            wait_until_browser_closes(
                browser,
                page,
                config["meeting_duration_seconds"],
            )

        except KeyboardInterrupt:
            log("Stopped manually.")

        except Exception as error:
            log(f"Error joining meeting: {error}")

        finally:
            log("Ending automated browser session.")

            if browser is not None:
                try:
                    browser.close()
                except PlaywrightError:
                    pass


if __name__ == "__main__":
    join_webex_meeting()
