# Testing Checklist and Results

This document tracks manual validation scenarios, expected behavior, actual outcomes, bugs found, and fixes applied.

## Manual Test Checklist

- [ ] Camera detects motion when person walks
- [ ] Inactivity alert triggers after threshold
- [ ] Email received for inactivity alert
- [ ] Odia speech recognized correctly
- [ ] Emergency intent triggers immediate alert
- [ ] Reminder plays at scheduled time
- [ ] Dashboard shows real-time status
- [ ] System runs 1 hour without crash
- [ ] Graceful shutdown on Ctrl+C
- [ ] Recovery from camera disconnection

## Execution Log

| Date | Tester | Environment | Commit/Version | Notes |
|---|---|---|---|---|
| YYYY-MM-DD |  |  |  |  |

## Expected vs Actual Results

| Test Item | Expected Result | Actual Result | Pass/Fail | Evidence (log/screenshot) |
|---|---|---|---|---|
| Camera detects motion when person walks | Motion state switches to ACTIVE and motion contour appears |  |  |  |
| Inactivity alert triggers after threshold | State switches to INACTIVE and alert entry is logged |  |  |  |
| Email received for inactivity alert | Caregiver inbox receives formatted high-severity email |  |  |  |
| Odia speech recognized correctly | Spoken Odia phrase transcribes with acceptable accuracy |  |  |  |
| Emergency intent triggers immediate alert | Emergency intent is classified and critical alert sent |  |  |  |
| Reminder plays at scheduled time | TTS reminder plays and reminder log marked triggered |  |  |  |
| Dashboard shows real-time status | Dashboard updates current state and latest logs |  |  |  |
| System runs 1 hour without crash | No unhandled exception, stable CPU/memory behavior |  |  |  |
| Graceful shutdown on Ctrl+C | Clean stop of threads/resources without corruption |  |  |  |
| Recovery from camera disconnection | System handles disconnect and resumes when reconnected |  |  |  |

## Bugs Found

| ID | Date | Severity | Module | Description | Repro Steps | Status |
|---|---|---|---|---|---|---|
| BUG-001 | YYYY-MM-DD |  |  |  |  | Open |

## Fixes Applied

| Fix ID | Date | Related Bug ID | Files Changed | Summary | Verification |
|---|---|---|---|---|---|
| FIX-001 | YYYY-MM-DD | BUG-001 |  |  |  |

## Notes

- For email tests, use safe test credentials and avoid real emergency messaging.
- Attach screenshots/GIFs and log snippets for failed scenarios.
- Re-run automated suite after each bug fix:

```bash
python -m unittest test_system.py -v
```
