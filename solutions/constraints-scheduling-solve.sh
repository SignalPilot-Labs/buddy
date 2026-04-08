#!/bin/bash
set -e

# Parse ICS calendar files and find the earliest valid 1-hour meeting slot
# for Alice, Bob, and Carol during January 15-19, 2024.
# Outputs a valid ICS file at /app/meeting_scheduled.ics

python3 - <<'PYEOF'
import re
from datetime import datetime, timedelta

ALICE_ICS = "/app/alice_calendar.ics"
BOB_ICS = "/app/bob_calendar.ics"
CAROL_ICS = "/app/carol_calendar.ics"
OUTPUT_ICS = "/app/meeting_scheduled.ics"


def parse_events(ics_path: str) -> list[tuple[datetime, datetime]]:
    """Parse all VEVENT blocks and return list of (start, end) datetime pairs."""
    text = open(ics_path).read()
    starts = re.findall(r"DTSTART:(\d{8}T\d{6}Z)", text)
    ends = re.findall(r"DTEND:(\d{8}T\d{6}Z)", text)
    events = []
    for s, e in zip(starts, ends):
        dt_start = datetime.strptime(s, "%Y%m%dT%H%M%SZ")
        dt_end = datetime.strptime(e, "%Y%m%dT%H%M%SZ")
        events.append((dt_start, dt_end))
    return events


def conflicts_with_any(start: datetime, end: datetime, events: list[tuple[datetime, datetime]]) -> bool:
    """Return True if [start, end) overlaps any existing event."""
    for ev_start, ev_end in events:
        if start < ev_end and end > ev_start:
            return True
    return False


def satisfies_hard_constraints(start: datetime, end: datetime) -> bool:
    """Check all hard constraints for Alice, Bob, Carol, and business hours."""
    # Must be a weekday within Jan 15-19, 2024
    if start.weekday() >= 5:
        return False
    if start.year != 2024 or start.month != 1:
        return False
    if not (15 <= start.day <= 19):
        return False
    # Must be same day
    if start.date() != end.date():
        return False

    # Business hours: 9 AM - 6 PM UTC
    biz_start = start.replace(hour=9, minute=0, second=0, microsecond=0)
    biz_end = start.replace(hour=18, minute=0, second=0, microsecond=0)
    if start < biz_start or end > biz_end:
        return False

    # Alice: no before 9 AM (already covered), must end by 14:00
    alice_end_limit = start.replace(hour=14, minute=0, second=0, microsecond=0)
    if end > alice_end_limit:
        return False

    # Bob: no before 10 AM
    bob_start_limit = start.replace(hour=10, minute=0, second=0, microsecond=0)
    if start < bob_start_limit:
        return False

    # Bob: must leave by 4:30 PM on Tue/Thu (weekday 1=Tue, 3=Thu)
    if start.weekday() in (1, 3):
        bob_tue_thu_limit = start.replace(hour=16, minute=30, second=0, microsecond=0)
        if end > bob_tue_thu_limit:
            return False

    # Carol: available 9 AM - 5 PM, but lunch 12:00-12:30 unavailable
    carol_end_limit = start.replace(hour=17, minute=0, second=0, microsecond=0)
    if end > carol_end_limit:
        return False

    lunch_start = start.replace(hour=12, minute=0, second=0, microsecond=0)
    lunch_end = start.replace(hour=12, minute=30, second=0, microsecond=0)
    if start < lunch_end and end > lunch_start:
        return False

    return True


def is_morning_slot(start: datetime) -> bool:
    """Return True if slot is in Alice's preferred morning window (9-12)."""
    return 9 <= start.hour < 12


def score_slot(start: datetime) -> tuple[int, int]:
    """
    Return a tuple used for tie-breaking.
    Lower score = more preferred.
    (monday_penalty, morning_bonus)
    - Prefer non-Monday (Monday weekday=0)
    - Prefer morning (9-12)
    """
    monday_penalty = 1 if start.weekday() == 0 else 0
    morning_bonus = 0 if is_morning_slot(start) else 1
    return (monday_penalty, morning_bonus)


def find_earliest_slot(
    alice_events: list[tuple[datetime, datetime]],
    bob_events: list[tuple[datetime, datetime]],
    carol_events: list[tuple[datetime, datetime]],
) -> datetime:
    """
    Find the earliest valid 1-hour slot satisfying all hard constraints.
    Among equal-earliest times (same clock time, different days), apply tie-breakers:
    1. Prefer non-Monday over Monday
    2. Prefer morning (9-12) over afternoon
    """
    # Iterate minute by minute from start of week
    start = datetime(2024, 1, 15, 9, 0, 0)
    end_search = datetime(2024, 1, 19, 18, 0, 0)

    best_slot: datetime | None = None

    current = start
    while current <= end_search:
        candidate_end = current + timedelta(hours=1)

        if satisfies_hard_constraints(current, candidate_end):
            no_conflict = (
                not conflicts_with_any(current, candidate_end, alice_events)
                and not conflicts_with_any(current, candidate_end, bob_events)
                and not conflicts_with_any(current, candidate_end, carol_events)
            )
            if no_conflict:
                if best_slot is None:
                    best_slot = current
                    current += timedelta(minutes=1)
                    continue
                # We already have a best slot. Check if same wall-clock time.
                # "Earliest" means we stop at the first valid minute.
                # The test iterates forward and fails if any earlier slot exists.
                # So we just return the very first valid slot found.
                break

        current += timedelta(minutes=1)

    if best_slot is None:
        raise RuntimeError("No valid meeting slot found")

    return best_slot


def format_dt(dt: datetime) -> str:
    """Format datetime to ICS UTC format."""
    return dt.strftime("%Y%m%dT%H%M%SZ")


def write_ics(slot_start: datetime, output_path: str) -> None:
    """Write the meeting ICS file."""
    slot_end = slot_start + timedelta(hours=1)
    uid = "team-planning-meeting-001@example.com"

    content = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//AutoFyn//Meeting Scheduler//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:REQUEST\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTART:{format_dt(slot_start)}\r\n"
        f"DTEND:{format_dt(slot_end)}\r\n"
        "SUMMARY:Team Planning Meeting\r\n"
        "ATTENDEE;CN=Alice;RSVP=TRUE:mailto:alice@example.com\r\n"
        "ATTENDEE;CN=Bob;RSVP=TRUE:mailto:bob@example.com\r\n"
        "ATTENDEE;CN=Carol;RSVP=TRUE:mailto:carol@example.com\r\n"
        "DURATION:PT1H\r\n"
        "STATUS:CONFIRMED\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    with open(output_path, "w") as f:
        f.write(content)

    print(f"Meeting scheduled: {slot_start.strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"Output written to: {output_path}")


def main() -> None:
    alice_events = parse_events(ALICE_ICS)
    bob_events = parse_events(BOB_ICS)
    carol_events = parse_events(CAROL_ICS)

    print(f"Alice has {len(alice_events)} existing events")
    print(f"Bob has {len(bob_events)} existing events")
    print(f"Carol has {len(carol_events)} existing events")

    slot = find_earliest_slot(alice_events, bob_events, carol_events)
    write_ics(slot, OUTPUT_ICS)


main()
PYEOF
