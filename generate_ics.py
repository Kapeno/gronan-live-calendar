import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

API_URL = (
    "https://prs-cdp-prod-webapiproxy.azurewebsites.net/"
    "api/glt/schedule/v2?scheduleTypes=Event"
)

TIMEZONE = ZoneInfo("Europe/Stockholm")

# Include any schedule whose internal title contains one of these strings.
INCLUDE_SCHEDULES = [
    "Grönan Live",
]

# Skip events whose title contains any of these strings.
EXCLUDE_EVENT_TITLES = [
    "Happy Hour",
]

# Default duration if the API doesn't provide an end time.
DEFAULT_DURATION = timedelta(hours=2)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def parse_datetime(value):
    if not value:
        return None

    return datetime.fromisoformat(value).replace(tzinfo=TIMEZONE)


def to_utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ------------------------------------------------------------
# Fetch data
# ------------------------------------------------------------

response = requests.get(API_URL, timeout=30)
response.raise_for_status()

data = response.json()["response"]

events = []

for schedule in data:
    title = schedule.get("internalTitle", "")

    if any(include in title for include in INCLUDE_SCHEDULES):
        events.extend(schedule["events"])


# ------------------------------------------------------------
# Clean & sort
# ------------------------------------------------------------

filtered_events = []

for event in events:

    title = event.get("title", "")

    if any(text in title for text in EXCLUDE_EVENT_TITLES):
        continue

    start = parse_datetime(event.get("startDateAndTime"))

    if start is None:
        continue

    end = parse_datetime(event.get("endDateAndTime"))

    if end is None:
        end = start + DEFAULT_DURATION

    filtered_events.append(
        {
            "uid": event["id"],
            "title": title,
            "description": event.get("description")
            or "Konsert på Gröna Lund",
            "start": start,
            "end": end,
            "cancelled": event.get("cancelled", False),
        }
    )

filtered_events.sort(key=lambda e: e["start"])


# ------------------------------------------------------------
# Generate ICS
# ------------------------------------------------------------

lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Grönan Live//Calendar//SV",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Grönan Live",
    "X-WR-TIMEZONE:Europe/Stockholm",
]

dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

for event in filtered_events:

    title = event["title"]

    if event["cancelled"]:
        title = "INSTÄLLD – " + title

    lines.extend(
        [
            "BEGIN:VEVENT",
            f"UID:{event['uid']}@gronan-live",
            f"DTSTAMP:{dtstamp}",
            f"SUMMARY:{title}",
            f"DESCRIPTION:{event['description']}",
            "LOCATION:Gröna Lund, Stockholm",
            f"DTSTART:{to_utc(event['start'])}",
            f"DTEND:{to_utc(event['end'])}",
            "END:VEVENT",
        ]
    )

lines.append("END:VCALENDAR")

with open("gronan-live.ics", "w", encoding="utf-8", newline="\r\n") as f:
    f.write("\r\n".join(lines))

print(f"Generated {len(filtered_events)} events.")
