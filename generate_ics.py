import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

API_URL = "https://prs-cdp-prod-webapiproxy.azurewebsites.net/api/glt/schedule/v2?scheduleTypes=Event"

TZ = ZoneInfo("Europe/Stockholm")

response = requests.get(API_URL, timeout=30)
response.raise_for_status()

events = response.json()["response"][0]["events"]


def parse_datetime(value):
    if not value:
        return None

    return datetime.fromisoformat(value).replace(tzinfo=TZ)


events = sorted(
    events,
    key=lambda e: e.get("startDateAndTime") or ""
)

lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Grönan Live//Calendar//SV",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Grönan Live",
    "X-WR-TIMEZONE:Europe/Stockholm",
]

now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

for event in events:

    start = parse_datetime(event.get("startDateAndTime"))

    if start is None:
        print(f"Skipping {event.get('title')} (missing start)")
        continue

    end = parse_datetime(event.get("endDateAndTime"))

    if end is None:
        end = start + timedelta(hours=2)

    title = event.get("title", "Unnamed event")

    if event.get("cancelled"):
        title = "INSTÄLLD – " + title

    description = event.get("description") or "Konsert på Gröna Lund"

    uid = event["id"]

    lines.extend([
        "BEGIN:VEVENT",
        f"UID:{uid}@gronan-live",
        f"DTSTAMP:{now}",
        f"SUMMARY:{title}",
        f"DESCRIPTION:{description}",
        "LOCATION:Gröna Lund, Stockholm",
        f"DTSTART:{start.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{end.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "END:VEVENT",
    ])

lines.append("END:VCALENDAR")

with open("gronan-live.ics", "w", encoding="utf-8", newline="\r\n") as f:
    f.write("\r\n".join(lines))

print(f"Wrote {len(events)} events.")
