"""
events_to_ics.py
----------------
Convert an Excel (.xlsx) or CSV file with events into a Google Calendar-compatible .ics file.

Required columns (case-insensitive):
  - title        : Event name
  - start_date   : e.g. 2026-04-01
  - start_time   : e.g. 09:00  (optional; omit for all-day events)
  - end_date     : e.g. 2026-04-01  (optional; defaults to start_date)
  - end_time     : e.g. 10:30  (optional; omit for all-day events)

Optional columns:
  - description  : Event notes
  - location     : Physical or virtual location
  - timezone     : e.g. Europe/Madrid (overrides --tz flag per row)

Usage:
  python events_to_ics.py events.xlsx -o calendar.ics --tz Europe/Madrid
  python events_to_ics.py events.csv  -o calendar.ics
"""

import argparse
import pandas as pd
import sys
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


# ── ICS helpers ──────────────────────────────────────────────────────────────


def ics_escape(text: str) -> str:
    """Escape special characters per RFC 5545."""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold(line: str) -> str:
    """Fold long lines per RFC 5545 (max 75 octets)."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    chunks, pos = [], 0
    while pos < len(encoded):
        limit = 75 if pos == 0 else 74  # first line 75, continuations 74 + space
        chunks.append(encoded[pos : pos + limit].decode("utf-8", errors="ignore"))
        pos += limit
    return "\r\n ".join(chunks)


def format_dt(dt: datetime, tz: ZoneInfo) -> str:
    """Format a datetime to ICS DTSTART/DTEND with TZID."""
    local = dt.astimezone(tz)
    return local.strftime("%Y%m%dT%H%M%S")


def make_uid() -> str:
    """Generate a unique identifier for the event."""
    return f"{uuid.uuid4()}@events-to-ics"


# ── Row parsing ───────────────────────────────────────────────────────────────


def parse_date(value) -> date:
    """Parse a date from various string formats."""
    if isinstance(value, (date, datetime)):
        return value.date() if isinstance(value, datetime) else value
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {value!r}")


def parse_time(value):
    """Return (hour, minute) or None if blank."""
    if not value or str(value).strip() in ("", "nan", "NaT", "None"):
        return None
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            t = datetime.strptime(str(value).strip(), fmt)
            return t.hour, t.minute
        except ValueError:
            continue
    raise ValueError(f"Cannot parse time: {value!r}")


def build_vevent(row: dict, default_tz: ZoneInfo) -> list[str]:
    """Build the VEVENT lines for an ICS event from a row dictionary."""
    cols = {k.lower().strip(): v for k, v in row.items()}

    title = cols.get("title") or cols.get("name") or cols.get("subject") or "Untitled"
    description = cols.get("description", "") or ""
    location = cols.get("location", "") or ""

    # Resolve timezone
    tz_str = str(cols.get("timezone", "")).strip()
    if tz_str and tz_str.lower() not in ("", "nan"):
        try:
            tz = ZoneInfo(tz_str)
        except ZoneInfoNotFoundError:
            print(f"  ⚠ Unknown timezone '{tz_str}', using default.", file=sys.stderr)
            tz = default_tz
    else:
        tz = default_tz

    start_date = parse_date(cols["start_date"])
    end_date_raw = cols.get("end_date") or cols.get("end date") or ""
    end_date = (
        parse_date(end_date_raw)
        if str(end_date_raw).strip() not in ("", "nan", "None")
        else start_date
    )

    start_time = parse_time(cols.get("start_time") or cols.get("start time") or "")
    end_time = parse_time(cols.get("end_time") or cols.get("end time") or "")

    now_stamp = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    uid = make_uid()

    lines = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{now_stamp}"]

    if start_time:
        dt_start = datetime(
            start_date.year, start_date.month, start_date.day, *start_time, tzinfo=tz
        )
        if end_time:
            dt_end = datetime(
                end_date.year, end_date.month, end_date.day, *end_time, tzinfo=tz
            )
        else:
            dt_end = dt_start + timedelta(hours=1)  # default 1-hour duration

        lines.append(f"DTSTART;TZID={tz.key}:{format_dt(dt_start, tz)}")
        lines.append(f"DTEND;TZID={tz.key}:{format_dt(dt_end, tz)}")
    else:
        # All-day event
        lines.append(f"DTSTART;VALUE=DATE:{start_date.strftime('%Y%m%d')}")
        next_day = end_date + timedelta(days=1)
        lines.append(f"DTEND;VALUE=DATE:{next_day.strftime('%Y%m%d')}")

    lines.append(fold(f"SUMMARY:{ics_escape(title)}"))
    if str(description).strip() and str(description).strip() != "nan":
        lines.append(fold(f"DESCRIPTION:{ics_escape(description)}"))
    if str(location).strip() and str(location).strip() != "nan":
        lines.append(fold(f"LOCATION:{ics_escape(location)}"))

    lines.append("END:VEVENT")
    return lines


# ── Main ──────────────────────────────────────────────────────────────────────


def load_file(path: Path) -> list[dict]:
    """Load event data from a CSV or Excel file into a list of dictionaries."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(path, dtype=str)
    elif suffix == ".csv":
        df = pd.read_csv(path, dtype=str, encoding='cp1252')
    else:
        sys.exit(f"Unsupported file type: {suffix}. Use .xlsx or .csv")
    df.columns = df.columns.str.strip().str.lower()
    df = df.dropna(how="all")
    return df.to_dict(orient="records")


def generate_ics(rows: list[dict], default_tz: ZoneInfo) -> str:
    """Generate the complete ICS calendar content from event rows."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//events-to-ics//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    errors = 0
    for i, row in enumerate(rows, start=2):  # row 2 = first data row
        try:
            lines.extend(build_vevent(row, default_tz))
        except Exception as e:
            print(f"  ✗ Row {i} skipped: {e}", file=sys.stderr)
            errors += 1

    lines.append("END:VCALENDAR")
    if errors:
        print(f"\n  {errors} row(s) skipped due to errors.", file=sys.stderr)
    return "\r\n".join(lines)


def main():
    """Parse arguments and run the conversion process."""
    parser = argparse.ArgumentParser(
        description="Convert Excel/CSV events to .ics for Google Calendar"
    )
    parser.add_argument("input", help="Path to .xlsx or .csv file")
    parser.add_argument(
        "-o",
        "--output",
        default="calendar.ics",
        help="Output .ics file (default: calendar.ics)",
    )
    parser.add_argument(
        "--tz",
        default="UTC",
        help="Default timezone, e.g. Europe/Madrid (default: UTC)",
    )
    args = parser.parse_args()

    try:
        tz = ZoneInfo(args.tz)
    except ZoneInfoNotFoundError:
        sys.exit(f"Unknown timezone: {args.tz}")

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"File not found: {input_path}")

    print(f"📂 Reading {input_path} ...")
    rows = load_file(input_path)
    print(f"   {len(rows)} event rows found.")

    print(f"🗓  Generating ICS (timezone: {args.tz}) ...")
    ics_content = generate_ics(rows, tz)

    output_path = Path(args.output)
    output_path.write_text(ics_content, encoding="utf-8")
    print(f"✅ Saved: {output_path}  ({len(rows)} events processed)")
    print("\nImport into Google Calendar:")
    print("  calendar.google.com → Settings → Import & Export → Import")


if __name__ == "__main__":
    main()
