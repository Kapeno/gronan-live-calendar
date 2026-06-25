#!/usr/bin/env python3

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

import requests
from zoneinfo import ZoneInfo


# ============================================================
# Configuration
# ============================================================

SCHEDULE_API = (
    "https://prs-cdp-prod-webapiproxy.azurewebsites.net/"
    "api/glt/schedule/v2?scheduleTypes=Event"
)

SHOWS_API = (
    "https://www.gronalund.com/"
    "page-data/konserter/page-data.json"
)

OUTPUT_FILE = "gronan-live.ics"

TIMEZONE = ZoneInfo("Europe/Stockholm")

DEFAULT_DURATION = timedelta(hours=2)


# Vilka scheman vill vi ha med?
INCLUDE_SCHEDULES = [
    "Grönan Live",
]

# Hela scheman som alltid ska ignoreras
EXCLUDE_SCHEDULES = [
]

# Eventtitlar som ska ignoreras
EXCLUDE_EVENT_TITLES = [
    "Happy Hour",
    "Parken abonnerad",
]


# ============================================================
# Helpers
# ============================================================

def contains_any(text: str, values: list[str]) -> bool:
    """Return True if text contains any string in values."""

    text = text.casefold()

    return any(value.casefold() in text for value in values)


def parse_datetime(value: str | None) -> datetime | None:
    """Convert API datetime to timezone aware datetime."""

    if not value:
        return None

    return datetime.fromisoformat(value).replace(
        tzinfo=TIMEZONE
    )


def utc(dt: datetime) -> str:
    """ICS UTC timestamp."""

    return (
        dt.astimezone(timezone.utc)
        .strftime("%Y%m%dT%H%M%SZ")
    )


def escape_ics(text: str) -> str:
    """
    Escape text according to RFC5545.
    """

    if not text:
        return ""

    text = text.replace("\\", "\\\\")
    text = text.replace(";", r"\;")
    text = text.replace(",", r"\,")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = text.replace("\n", r"\n")

    return text


def clean_description(text: str) -> str:
    """
    Remove excessive whitespace and line breaks.
    """

    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def fetch_json(url: str) -> dict:
    """
    Download JSON and raise if request fails.
    """

    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "gronan-live-calendar"
        },
    )

    response.raise_for_status()

    return response.json()
	
# ============================================================
# Load schedule API
# ============================================================

print("Downloading schedule...")

schedule_data = fetch_json(SCHEDULE_API)

schedule_events = []

for schedule in schedule_data["response"]:

    schedule_title = schedule.get("internalTitle", "")

    if not contains_any(
        schedule_title,
        INCLUDE_SCHEDULES,
    ):
        continue

    if contains_any(
        schedule_title,
        EXCLUDE_SCHEDULES,
    ):
        continue

    for event in schedule["events"]:

        event["_schedule"] = schedule_title

        schedule_events.append(event)

print(f"Loaded {len(schedule_events)} scheduled events.")


# ============================================================
# Load Swedish concert metadata
# ============================================================

print("Downloading Swedish concert metadata...")

page_data = fetch_json(SHOWS_API)

show_lookup: Dict[str, Dict[str, Any]] = {}

blocks = (
    page_data["result"]["data"]
    ["allContentfulShowBlock"]["nodes"]
)

for block in blocks:

    title = block.get("title")

    if not title:
        continue

    info = {
        "title": title,
        "description": clean_description(
            (
                block.get("preamble") or {}
            ).get("preamble", "")
        ),
        "location": block.get("location") or "",
        "url": "",
        "externalEntryId": None,
    }

    page_link = block.get("pageLink")

    if page_link:

        slug = page_link.get("slug")

        if slug:
            info["url"] = (
                "https://www.gronalund.com"
                + slug
            )

    external = block.get("externalEntry")

    if external:
        info["externalEntryId"] = (
            external.get("externalEntryId")
        )

    show_lookup[title.casefold()] = info


print(
    f"Loaded metadata for "
    f"{len(show_lookup)} concerts."
)


# ============================================================
# Merge API + metadata
# ============================================================

events = []

for event in schedule_events:

    title = event.get("title", "")

    if contains_any(
        title,
        EXCLUDE_EVENT_TITLES,
    ):
        continue

    start = parse_datetime(
        event.get("startDateAndTime")
    )

    if start is None:
        continue

    end = parse_datetime(
        event.get("endDateAndTime")
    )

    if end is None:
        end = start + DEFAULT_DURATION

    metadata = show_lookup.get(
        title.casefold(),
        {},
    )

    description = (
        metadata.get("description")
        or event.get("description")
        or ""
    )

    location = (
        metadata.get("location")
        or "Gröna Lund"
    )

    url = metadata.get("url", "")

    events.append(
        {
            "uid": event["id"],
            "title": title,
            "description": description,
            "location": location,
            "url": url,
            "start": start,
            "end": end,
            "cancelled": event.get(
                "cancelled",
                False,
            ),
        }
    )

events.sort(
    key=lambda e: e["start"]
)

print(
    f"Prepared {len(events)} calendar events."
)
# ============================================================
# ICS writer
# ============================================================

def fold_ics_line(line: str) -> list[str]:
    """
    Fold long ICS lines according to RFC5545.
    Max 75 octets (we approximate with 73 chars).
    """

    MAX = 73

    if len(line) <= MAX:
        return [line]

    lines = []

    while len(line) > MAX:
        lines.append(line[:MAX])
        line = " " + line[MAX:]

    lines.append(line)

    return lines


def write_line(lines: list[str], line: str):
    """
    Write one folded ICS line.
    """

    for part in fold_ics_line(line):
        lines.append(part)


# ============================================================
# Build calendar
# ============================================================

print("Generating ICS...")

lines = []

lines.extend([
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Grönan Live Calendar//SV",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Grönan Live",
    "X-WR-TIMEZONE:Europe/Stockholm",
])

dtstamp = utc(datetime.now(timezone.utc))

for event in events:

    lines.append("BEGIN:VEVENT")

    write_line(
        lines,
        f"UID:{event['uid']}@gronan-live",
    )

    write_line(
        lines,
        f"DTSTAMP:{dtstamp}",
    )

    write_line(
        lines,
        f"SUMMARY:{escape_ics(event['title'])}",
    )

    write_line(
        lines,
        f"DTSTART:{utc(event['start'])}",
    )

    write_line(
        lines,
        f"DTEND:{utc(event['end'])}",
    )

    if event["location"]:
        write_line(
            lines,
            f"LOCATION:{escape_ics(event['location'])}",
        )

    description = event["description"]

    if event["url"]:

        if description:
            description += "\n\n"

        description += (
            "Läs mer:\n"
            + event["url"]
        )

    if description:

        write_line(
            lines,
            "DESCRIPTION:"
            + escape_ics(description),
        )

    if event["url"]:
        write_line(
            lines,
            f"URL:{event['url']}",
        )

    if event["cancelled"]:

        write_line(
            lines,
            "STATUS:CANCELLED",
        )

    lines.append("END:VEVENT")

lines.append("END:VCALENDAR")


# ============================================================
# Save
# ============================================================

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8",
    newline="\r\n",
) as f:

    f.write("\r\n".join(lines))

print()
print("---------------------------------------")
print(f"Generated {len(events)} events.")
print(f"Saved to {OUTPUT_FILE}")
print("---------------------------------------")
