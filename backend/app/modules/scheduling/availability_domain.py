"""Pure free-window calculation, including adjacent or overlapping blockers."""
from datetime import datetime


def free_windows(start: datetime, blockers: list[tuple[datetime, datetime, str]]):
    merged: list[tuple[datetime, datetime, str]] = []
    for begin, end, evidence_id in sorted(blockers):
        if end <= start:
            continue
        if merged and begin <= merged[-1][1]:
            previous_begin, previous_end, previous_id = merged[-1]
            merged[-1] = (previous_begin, max(previous_end, end), previous_id)
        else:
            merged.append((begin, end, evidence_id))
    cursor, previous_id = start, None
    windows = []
    for begin, end, evidence_id in merged:
        if begin > cursor:
            windows.append((cursor, begin, previous_id))
        cursor, previous_id = max(cursor, end), evidence_id
    windows.append((cursor, None, previous_id))
    return windows
