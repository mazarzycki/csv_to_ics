# CSV to ICS Converter

A Python script to convert event data from CSV or Excel files into Google Calendar-compatible ICS (iCalendar) files. Easily import your events into Google Calendar or other calendar applications that support the ICS format.

## Features

- **Multiple Input Formats**: Supports both CSV and Excel (.xlsx, .xlsm, .xls) files
- **Flexible Date/Time Parsing**: Handles various date and time formats automatically
- **Timezone Support**: Specify default timezone with `--tz` flag, or per-event with a timezone column
- **All-Day Events**: Omit start/end times for all-day events
- **Error Handling**: Skips invalid rows and reports errors
- **RFC 5545 Compliant**: Generates properly formatted ICS files
- **Command-Line Interface**: Simple CLI with options for input, output, and timezone

## Installation

### Prerequisites

- Python 3.6 or higher
- Required Python packages: `pandas`, `openpyxl` (for Excel support)

### Install Dependencies

```bash
pip install pandas openpyxl
```

Or create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install pandas openpyxl
```

## Usage

### Basic Usage

```bash
python events_to_ics.py events.csv -o calendar.ics
```

### With Timezone

```bash
python events_to_ics.py events.xlsx -o calendar.ics --tz Europe/Madrid
```

### Command-Line Options

- `input`: Path to the input CSV or Excel file (required)
- `-o, --output`: Output ICS file path (default: calendar.ics)
- `--tz`: Default timezone (default: UTC). Use IANA timezone names like 'America/New_York' or 'Europe/London'

## Input File Format

### Required Columns (case-insensitive)

- **title** (or **name**, **subject**): Event name/title
- **start_date**: Start date in formats like YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, DD-MM-YYYY
- **start_time**: Start time in formats like HH:MM, HH:MM:SS, HH:MM AM/PM (optional for all-day events)
- **end_date**: End date (optional, defaults to start_date)
- **end_time**: End time (optional for all-day events)

### Optional Columns

- **description**: Event description/notes
- **location**: Physical or virtual location
- **timezone**: Per-event timezone override (IANA name, e.g., Europe/Madrid)

### Example CSV

```csv
title,start_date,start_time,end_date,end_time,description,location,timezone
"Team Meeting",2024-01-15,09:00,2024-01-15,10:00,"Weekly team sync","Conference Room A",
"Project Deadline",2024-01-20,,,,"Submit final report",,
"Conference",2024-02-01,09:00,2024-02-03,17:00,"Annual tech conference","Convention Center","America/New_York"
```

## Examples

### Convert CSV to ICS

```bash
python events_to_ics.py events.csv -o my_calendar.ics --tz UTC
```

### Convert Excel to ICS with Timezone

```bash
python events_to_ics.py events.xlsx -o calendar.ics --tz Europe/Paris
```

### Import into Google Calendar

1. Go to [Google Calendar](https://calendar.google.com)
2. Click the gear icon (Settings) → Settings
3. Click "Import & Export" in the left sidebar
4. Click "Select file from your computer" and choose your .ics file
5. Select the calendar to import into
6. Click "Import"

## Requirements

- Python 3.6+
- pandas
- openpyxl (for Excel files)
- zoneinfo (built-in for Python 3.9+, install backports.zoneinfo for older versions)

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests if applicable
4. Run the script to ensure it works
5. Commit your changes: `git commit -am 'Add some feature'`
6. Push to the branch: `git push origin feature-name`
7. Submit a pull request

### Development Setup

```bash
git clone https://github.com/yourusername/csv-to-ics.git
cd csv-to-ics
pip install -r requirements.txt
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

- Built with Python and pandas
- ICS format follows RFC 5545 specification
- Inspired by the need for easy calendar data import

## Troubleshooting

### Common Issues

- **UnicodeDecodeError**: Your CSV file may not be UTF-8 encoded. The script now uses cp1252 encoding for CSV files. If you encounter issues, try converting your CSV to UTF-8.
- **Date parsing errors**: Ensure dates are in supported formats. The script tries multiple formats automatically.
- **Timezone errors**: Use valid IANA timezone names (e.g., 'America/New_York', not 'EST').

### Error Messages

The script will skip invalid rows and print error messages to stderr. Check the output for any issues.

## Changelog

### v1.0.0
- Initial release
- Support for CSV and Excel input
- Timezone handling
- Basic error handling

## Support

If you encounter issues or have questions:

1. Check the troubleshooting section above
2. Search existing issues on GitHub
3. Create a new issue with your error message and input file sample

---

Made with ❤️ for easy calendar management.