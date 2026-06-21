import requests
from datetime import datetime
from zoneinfo import ZoneInfo

API_URL = "https://prs-cdp-prod-webapiproxy.azurewebsites.net/api/glt/schedule/v2?scheduleTypes=Event"

data = requests.get(API_URL, timeout=30).json()

events = data["response"][0]["events"]

lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Grönan Live//Calendar//SV",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
]

for event in events:
    if event.get("cancelled"):
        continue

    start = datetime.fromisoformat(event["startDateAndTime"]).replace(
        tzinfo=ZoneInfo("Europe/Stockholm")
    )

    end = datetime.fromisoformat(event["endDateAndTime"]).replace(
        tzinfo=ZoneInfo("Europe/Stockholm")
    )

    uid = event["id"]
    title = event["title"]

    lines.extend([
        "BEGIN:VEVENT",
        f"UID:{uid}@gronan-live",
        f"SUMMARY:{title}",
        f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
        "LOCATION:Gröna Lund, Stockholm",
        "END:VEVENT",
    ])

lines.append("END:VCALENDAR")

with open("gronan-live.ics", "w", encoding="utf-8") as f:
    f.write("\r\n".join(lines))
