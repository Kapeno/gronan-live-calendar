import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ============================================================
# Configuration
# ============================================================

API_URL = (
    "https://prs-cdp-prod-webapiproxy.azurewebsites.net/"
    "api/glt/schedule/v2?scheduleTypes=Event"
)

TIMEZONE = ZoneInfo("Europe/Stockholm")

# Schedules to include
INCLUDE_SCHEDULES = [
    "Grönan Live",
    # "Dansband",
    # "FYRE",
    # "Salsa",
]

# Skip entire schedules
EXCLUDE_SCHEDULES = [
    "GLT - Öl & sånt",
]

# Skip individual events whose title contains these strings
EXCLUDE_EVENT_TITLES = [
    "Happy Hour",
    "Parken abonnerad",
]

DEFAULT_DURATION = timedelta(hours=2)

# ============================================================
# Helper functions
# ============================================================


def parse_datetime(value):
    if not value:
        return None

    return datetime.fromisoformat(value).replace(tzinfo=TIMEZONE)


def utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def contains_any(text, patterns):
    return any(pattern.lower() in text.lower() for pattern in patterns)


# ============================================================
# Download data
# ============================================================

response = requests.get(API_URL, timeout=30)
response.raise_for_status()

schedules = response.json()["response"]

events = []

for schedule in schedules:

    schedule_title = schedule.get("internalTitle", "")

    if not contains_any(schedule_title, INCLUDE_SCHEDULES):
        continue

    if contains_any(schedule_title, EXCLUDE_SCHEDULES):
        continue

    for event in schedule["events"]:
        event["_schedule"] = schedule_title
        events.append(event)

# ============================================================
# Filter & normalize
# ============================================================

filtered = []

for event in events:

    title = event.get("title", "")

    if contains_any(title, EXCLUDE_EVENT_TITLES):
        continue

    start = parse_datetime(event.get("startDateAndTime"))

    if start is None:
        continue

    end = parse_datetime(event.get("endDateAndTime"))

    if end is None:
        end = start + DEFAULT_DURATION

    filtered.append(
        {
            "uid": event["id"],
            "title": title,
            "description": event.get("description")
            or f"Schema: {event['_schedule']}",
            "start": start,
            "end": end,
            "cancelled": event.get("cancelled", False),
            "schedule": event["_schedule"],
        }
    )

filtered.sort(key=lambda e: e["start"])

# ============================================================
# Generate ICS
# ============================================================

lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Grönan Live Calendar//SV",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Grönan Live",
    "X-WR-TIMEZONE:Europe/Stockholm",
]

dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

for event in filtered:

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
            f"DTSTART:{utc(event['start'])}",
            f"DTEND:{utc(event['end'])}",
            "END:VEVENT",
        ]
    )

lines.append("END:VCALENDAR")

with open(
    "gronan-live.ics",
    "w",
    encoding="utf-8",
    newline="\r\n",
) as f:
    f.write("\r\n".join(lines))

print(f"Generated {len(filtered)} events.")
