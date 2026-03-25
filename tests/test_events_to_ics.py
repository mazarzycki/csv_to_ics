import pytest
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo
import sys
import os

# Add the parent directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from events_to_ics import (
    ics_escape, fold, format_dt, make_uid, parse_date, parse_time,
    build_vevent, load_file, generate_ics
)


class TestICSEscape:
    def test_escape_special_chars(self):
        assert ics_escape("Hello; World,") == "Hello\\; World\\,"
        assert ics_escape("Line\nBreak") == "Line\\nBreak"
        assert ics_escape("Back\\slash") == "Back\\\\slash"

    def test_no_special_chars(self):
        assert ics_escape("Hello World") == "Hello World"


class TestFold:
    def test_fold_short_line(self):
        line = "SHORT LINE"
        assert fold(line) == line

    def test_fold_long_line(self):
        long_line = "A" * 80
        folded = fold(long_line)
        assert len(folded.split('\r\n ')) == 2
        assert folded.startswith("A" * 75 + "\r\n A")

    def test_fold_non_ascii(self):
        # Non-ASCII characters: é is 2 bytes in UTF-8
        line = "Café " * 20  # Each "Café " is 6 bytes, 20*6=120 >75
        folded = fold(line)
        assert len(folded.split('\r\n ')) == 2


class TestFormatDT:
    def test_format_datetime(self):
        tz = ZoneInfo("UTC")
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=tz)
        expected = "20240101T120000"
        assert format_dt(dt, tz) == expected


class TestMakeUID:
    def test_make_uid_format(self):
        uid = make_uid()
        assert uid.endswith("@events-to-ics")
        assert len(uid) > 20  # UUID is 36 chars + @ + domain

    def test_make_uid_unique(self):
        uid1 = make_uid()
        uid2 = make_uid()
        assert uid1 != uid2


class TestParseDate:
    def test_parse_date_yyyy_mm_dd(self):
        result = parse_date("2024-01-01")
        assert result == date(2024, 1, 1)

    def test_parse_date_dd_mm_yyyy(self):
        result = parse_date("01/01/2024")
        assert result == date(2024, 1, 1)

    def test_parse_date_mm_dd_yyyy(self):
        result = parse_date("01/01/2024")
        assert result == date(2024, 1, 1)

    def test_parse_date_datetime(self):
        dt = datetime(2024, 1, 1, 12, 0)
        result = parse_date(dt)
        assert result == date(2024, 1, 1)

    def test_parse_date_ambiguous(self):
        with pytest.raises(ValueError, match="Ambiguous date format"):
            parse_date("01/02/2024")


class TestParseTime:
    def test_parse_time_hh_mm(self):
        result = parse_time("10:30")
        assert result == (10, 30)

    def test_parse_time_hh_mm_ss(self):
        result = parse_time("10:30:45")
        assert result == (10, 30)

    def test_parse_time_12_hour(self):
        result = parse_time("10:30 AM")
        assert result == (10, 30)

    def test_parse_time_blank(self):
        assert parse_time("") is None
        assert parse_time("nan") is None

    def test_parse_time_invalid(self):
        with pytest.raises(ValueError):
            parse_time("invalid-time")


class TestBuildVEvent:
    def test_build_vevent_timed_event(self):
        row = {
            "title": "Test Event",
            "start_date": "2024-01-01",
            "start_time": "10:00",
            "end_date": "2024-01-01",
            "end_time": "11:00",
            "description": "Test description",
            "location": "Test location"
        }
        tz = ZoneInfo("UTC")
        lines = build_vevent(row, tz)
        assert "BEGIN:VEVENT" in lines
        assert "END:VEVENT" in lines
        assert any("DTSTART;TZID=UTC:20240101T100000" in line for line in lines)
        assert any("DTEND;TZID=UTC:20240101T110000" in line for line in lines)
        assert any("SUMMARY:Test Event" in line for line in lines)

    def test_build_vevent_all_day(self):
        row = {
            "title": "All Day Event",
            "start_date": "2024-01-02",
            "end_date": "2024-01-03"
        }
        tz = ZoneInfo("UTC")
        lines = build_vevent(row, tz)
        assert any("DTSTART;VALUE=DATE:20240102" in line for line in lines)
        assert any("DTEND;VALUE=DATE:20240104" in line for line in lines)  # Next day

    def test_build_vevent_invalid_timezone(self):
        row = {
            "title": "Event with Invalid TZ",
            "start_date": "2024-01-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "Invalid/Timezone"
        }
        tz = ZoneInfo("UTC")
        lines = build_vevent(row, tz)
        # Should use default tz
        assert any("DTSTART;TZID=UTC:20240101T100000" in line for line in lines)


class TestLoadFile:
    def test_load_csv_file(self):
        test_file = Path(__file__).parent / "test_events.csv"
        rows = load_file(test_file)
        assert len(rows) == 3
        assert rows[0]["title"] == "Test Event"
        assert rows[1]["title"] == "All Day Event"

    def test_load_unsupported_file(self):
        with pytest.raises(SystemExit):
            load_file(Path("test.txt"))


class TestGenerateICS:
    def test_generate_ics_basic(self):
        rows = [
            {
                "title": "Test Event",
                "start_date": "2024-01-01",
                "start_time": "10:00",
                "end_time": "11:00"
            }
        ]
        tz = ZoneInfo("UTC")
        ics_content = generate_ics(rows, tz)
        assert "BEGIN:VCALENDAR" in ics_content
        assert "END:VCALENDAR" in ics_content
        assert "BEGIN:VEVENT" in ics_content
        assert "END:VEVENT" in ics_content

    def test_generate_ics_with_errors(self):
        rows = [
            {"title": "Good Event", "start_date": "2024-01-01", "start_time": "10:00", "end_time": "11:00"},
            {"title": "Bad Event", "start_date": "invalid"}  # This will cause error
        ]
        tz = ZoneInfo("UTC")
        ics_content = generate_ics(rows, tz)
        # Should still generate ICS with the good event
        assert "Good Event" in ics_content
        assert "Bad Event" not in ics_content  # Bad event skipped

    def test_generate_ics_missing_required_column(self):
        rows = [
            {"title": "Event without start_date"}
        ]
        tz = ZoneInfo("UTC")
        ics_content = generate_ics(rows, tz)
        # Should skip the event
        assert "Event without start_date" not in ics_content