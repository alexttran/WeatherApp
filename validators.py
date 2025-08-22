from datetime import date

# Get date
def parse_iso_date(s: str) -> date:
    return date.fromisoformat(s)  # raises ValueError on bad input

# Validate date ranges
def validate_range(start_s: str, end_s: str) -> tuple[date, date]:
    start = parse_iso_date(start_s)
    end = parse_iso_date(end_s)
    if end < start:
        raise ValueError("end_date must be on/after start_date")
    return start, end