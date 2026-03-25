import pytest
import tempfile
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

from events_to_ics import (
    ics_escape,
    fold,
    format_dt,
    make_uid,
    parse_date,
    parse_time,
    build_vevent,
    load_file,
    generate_ics,
    DATE_FORMAT_SHORTCUTS,
)


# ── ICS helpers ──────────────────────────────────────────────────────────────


class TestICSEscape:
    def test_escape_special_chars(self):
        assert ics_escape("Hello; World,") == "Hello\\; World\\,"
        assert ics_escape("Line\nBreak") == "Line\\nBreak"
        assert ics_escape("Back\\slash") == "Back\\\\slash"

    def test_no_special_chars(self):
        assert ics_escape("Hello World") == "Hello World"

    def test_combined(self):
        assert ics_escape("a\\b;c,d\ne") == "a\\\\b\\;c\\,d\\ne"


class TestFold:
    def test_short_line_unchanged(self):
        line = "SHORT LINE"
        assert fold(line) == line

    def test_exactly_75_bytes_unchanged(self):
        line = "A" * 75
        assert fold(line) == line

    def test_76_bytes_folded(self):
        line = "A" * 76
        folded = fold(line)
        assert "\r\n " in folded

    def test_long_line(self):
        long_line = "A" * 200
        folded = fold(long_line)
        parts = folded.split("\r\n ")
        assert len(parts) >= 3

    def test_non_ascii(self):
        line = "Café " * 20  # "Café " = 6 bytes in UTF-8
        folded = fold(line)
        assert "\r\n " in folded


class TestFormatDT:
    def test_utc(self):
        tz = ZoneInfo("UTC")
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=tz)
        assert format_dt(dt, tz) == "20240101T120000"

    def test_timezone_conversion(self):
        utc = ZoneInfo("UTC")
        madrid = ZoneInfo("Europe/Madrid")
        dt = datetime(2024, 7, 1, 12, 0, 0, tzinfo=utc)
        formatted = format_dt(dt, madrid)
        assert formatted == "20240701T140000"  # UTC+2 in summer


class TestMakeUID:
    def test_format(self):
        uid = make_uid()
        assert uid.endswith("@events-to-ics")
        assert len(uid) > 20

    def test_uniqueness(self):
        uids = {make_uid() for _ in range(100)}
        assert len(uids) == 100


# ── Date parsing (the critical edge cases) ──────────────────────────────────


class TestParseDate:
    # --- ISO / unambiguous formats ---

    def test_iso_format(self):
        assert parse_date("2024-01-15") == date(2024, 1, 15)

    def test_iso_format_end_of_year(self):
        assert parse_date("2024-12-31") == date(2024, 12, 31)

    # --- Day-first unambiguous (day > 12 forces dd/mm/yyyy) ---

    def test_day_first_unambiguous(self):
        assert parse_date("25/01/2024") == date(2024, 1, 25)

    def test_day_first_high_day(self):
        assert parse_date("31/12/2024") == date(2024, 12, 31)

    # --- Month-first unambiguous (second number > 12 forces mm/dd/yyyy) ---

    def test_month_first_unambiguous(self):
        assert parse_date("01/25/2024") == date(2024, 1, 25)

    def test_month_first_high_day(self):
        assert parse_date("12/31/2024") == date(2024, 12, 31)

    # --- Ambiguous dates raise ValueError ---

    def test_ambiguous_date_raises(self):
        with pytest.raises(ValueError, match="Ambiguous"):
            parse_date("01/02/2024")

    def test_ambiguous_date_symmetric(self):
        with pytest.raises(ValueError, match="Ambiguous"):
            parse_date("03/04/2024")

    # --- Identical under both formats (not ambiguous: both parse to same date) ---

    def test_same_day_month(self):
        assert parse_date("05/05/2024") == date(2024, 5, 5)

    # --- Datetime objects pass through ---

    def test_datetime_input(self):
        dt = datetime(2024, 6, 15, 9, 30)
        assert parse_date(dt) == date(2024, 6, 15)

    def test_date_input(self):
        d = date(2024, 6, 15)
        assert parse_date(d) == date(2024, 6, 15)

    # --- Dash-separated dd-mm-yyyy ---

    def test_dash_day_month(self):
        assert parse_date("25-01-2024") == date(2024, 1, 25)

    # --- Invalid ---

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_date("not-a-date")

    def test_invalid_date_values(self):
        with pytest.raises(ValueError):
            parse_date("32/01/2024")


class TestParseDateExplicitFormat:
    """Tests for the --date-format feature."""

    def test_explicit_dmy_resolves_ambiguity(self):
        assert parse_date("01/02/2024", "DMY") == date(2024, 2, 1)

    def test_explicit_mdy_resolves_ambiguity(self):
        assert parse_date("01/02/2024", "MDY") == date(2024, 1, 2)

    def test_explicit_ymd(self):
        assert parse_date("2024-03-15", "YMD") == date(2024, 3, 15)

    def test_explicit_strftime_pattern(self):
        assert parse_date("15.03.2024", "%d.%m.%Y") == date(2024, 3, 15)

    def test_explicit_format_mismatch_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_date("2024-01-01", "DMY")

    def test_shortcuts_case_insensitive(self):
        assert parse_date("01/02/2024", "dmy") == date(2024, 2, 1)


class TestDateFormatShortcuts:
    def test_all_shortcuts_present(self):
        assert set(DATE_FORMAT_SHORTCUTS.keys()) == {"DMY", "MDY", "YMD"}


# ── Time parsing ─────────────────────────────────────────────────────────────


class TestParseTime:
    def test_24h(self):
        assert parse_time("10:30") == (10, 30)

    def test_24h_seconds(self):
        assert parse_time("10:30:45") == (10, 30)

    def test_12h_am(self):
        assert parse_time("10:30 AM") == (10, 30)

    def test_12h_pm(self):
        assert parse_time("02:30 PM") == (14, 30)

    def test_12h_no_space(self):
        assert parse_time("02:30PM") == (14, 30)

    def test_midnight(self):
        assert parse_time("00:00") == (0, 0)

    def test_blank_values(self):
        assert parse_time("") is None
        assert parse_time("nan") is None
        assert parse_time("NaT") is None
        assert parse_time("None") is None
        assert parse_time(None) is None

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Cannot parse time"):
            parse_time("25:99")


# ── VEVENT building ──────────────────────────────────────────────────────────


class TestBuildVEvent:
    def test_timed_event(self):
        row = {
            "title": "Standup",
            "start_date": "2024-01-15",
            "start_time": "09:00",
            "end_date": "2024-01-15",
            "end_time": "09:30",
            "description": "Daily standup",
            "location": "Room 1",
        }
        lines = build_vevent(row, ZoneInfo("UTC"))
        assert "BEGIN:VEVENT" in lines
        assert "END:VEVENT" in lines
        assert any("DTSTART;TZID=UTC:20240115T090000" in l for l in lines)
        assert any("DTEND;TZID=UTC:20240115T093000" in l for l in lines)
        assert any("SUMMARY:Standup" in l for l in lines)
        assert any("DESCRIPTION:Daily standup" in l for l in lines)
        assert any("LOCATION:Room 1" in l for l in lines)

    def test_all_day_event(self):
        row = {"title": "Holiday", "start_date": "2024-12-25"}
        lines = build_vevent(row, ZoneInfo("UTC"))
        assert any("DTSTART;VALUE=DATE:20241225" in l for l in lines)
        assert any("DTEND;VALUE=DATE:20241226" in l for l in lines)

    def test_multi_day_all_day(self):
        row = {"title": "Trip", "start_date": "2024-07-01", "end_date": "2024-07-05"}
        lines = build_vevent(row, ZoneInfo("UTC"))
        assert any("DTSTART;VALUE=DATE:20240701" in l for l in lines)
        assert any("DTEND;VALUE=DATE:20240706" in l for l in lines)  # exclusive end

    def test_default_one_hour_duration(self):
        row = {"title": "Quick chat", "start_date": "2024-03-01", "start_time": "14:00"}
        lines = build_vevent(row, ZoneInfo("UTC"))
        assert any("DTSTART;TZID=UTC:20240301T140000" in l for l in lines)
        assert any("DTEND;TZID=UTC:20240301T150000" in l for l in lines)

    def test_per_event_timezone(self):
        row = {
            "title": "NYC Call",
            "start_date": "2024-06-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "America/New_York",
        }
        lines = build_vevent(row, ZoneInfo("UTC"))
        assert any("TZID=America/New_York" in l for l in lines)

    def test_invalid_timezone_falls_back(self):
        row = {
            "title": "Event",
            "start_date": "2024-01-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "Fake/Zone",
        }
        lines = build_vevent(row, ZoneInfo("UTC"))
        assert any("TZID=UTC" in l for l in lines)

    def test_date_format_passed_through(self):
        row = {"title": "Event", "start_date": "01/02/2024", "start_time": "10:00"}
        lines = build_vevent(row, ZoneInfo("UTC"), date_format="MDY")
        assert any("20240102" in l for l in lines)  # Jan 2

    def test_special_chars_escaped(self):
        row = {
            "title": "Team; sync, catch-up",
            "start_date": "2024-01-01",
            "description": "Notes:\nBring laptop",
        }
        lines = build_vevent(row, ZoneInfo("UTC"))
        summary_line = next(l for l in lines if "SUMMARY:" in l)
        assert "\\;" in summary_line
        assert "\\," in summary_line

    def test_column_name_aliases(self):
        row = {"name": "By Name", "start_date": "2024-01-01"}
        lines = build_vevent(row, ZoneInfo("UTC"))
        assert any("SUMMARY:By Name" in l for l in lines)

        row2 = {"subject": "By Subject", "start_date": "2024-01-01"}
        lines2 = build_vevent(row2, ZoneInfo("UTC"))
        assert any("SUMMARY:By Subject" in l for l in lines2)


# ── File loading ─────────────────────────────────────────────────────────────


class TestLoadFile:
    def test_load_csv(self):
        test_file = Path(__file__).parent / "test_events.csv"
        rows = load_file(test_file)
        assert len(rows) == 3
        assert rows[0]["title"] == "Test Event"

    def test_load_csv_utf8(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title,start_date\n")
            f.write("Réunion café,2024-03-01\n")
            tmp = Path(f.name)
        try:
            rows = load_file(tmp)
            assert rows[0]["title"] == "Réunion café"
        finally:
            tmp.unlink()

    def test_load_csv_cp1252_fallback(self):
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".csv", delete=False
        ) as f:
            f.write("title,start_date\n".encode("cp1252"))
            f.write("Stra\xdfe,2024-03-01\n".encode("cp1252"))  # ß in cp1252
            tmp = Path(f.name)
        try:
            rows = load_file(tmp)
            assert rows[0]["title"] == "Straße"
        finally:
            tmp.unlink()

    def test_load_csv_explicit_encoding(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="latin-1"
        ) as f:
            f.write("title,start_date\n")
            f.write("Stra\u00dfe,2024-03-01\n")
            tmp = Path(f.name)
        try:
            rows = load_file(tmp, encoding="latin-1")
            assert rows[0]["title"] == "Straße"
        finally:
            tmp.unlink()

    def test_unsupported_extension(self):
        with pytest.raises(SystemExit):
            load_file(Path("file.txt"))

    def test_column_names_normalized(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("  Title , Start_Date \n")
            f.write("Test,2024-01-01\n")
            tmp = Path(f.name)
        try:
            rows = load_file(tmp)
            assert "title" in rows[0]
            assert "start_date" in rows[0]
        finally:
            tmp.unlink()


# ── Full ICS generation ──────────────────────────────────────────────────────


class TestGenerateICS:
    def test_valid_events(self):
        rows = [
            {"title": "A", "start_date": "2024-01-01", "start_time": "10:00", "end_time": "11:00"},
            {"title": "B", "start_date": "2024-01-02"},
        ]
        ics = generate_ics(rows, ZoneInfo("UTC"))
        assert ics.startswith("BEGIN:VCALENDAR")
        assert ics.endswith("END:VCALENDAR")
        assert ics.count("BEGIN:VEVENT") == 2

    def test_bad_rows_skipped(self):
        rows = [
            {"title": "Good", "start_date": "2024-01-01"},
            {"title": "Bad"},  # missing start_date
        ]
        ics = generate_ics(rows, ZoneInfo("UTC"))
        assert "Good" in ics
        assert "Bad" not in ics

    def test_crlf_line_endings(self):
        rows = [{"title": "E", "start_date": "2024-01-01"}]
        ics = generate_ics(rows, ZoneInfo("UTC"))
        assert "\r\n" in ics

    def test_date_format_threaded_through(self):
        rows = [{"title": "E", "start_date": "01/02/2024"}]
        ics = generate_ics(rows, ZoneInfo("UTC"), date_format="DMY")
        assert "20240201" in ics  # Feb 1
