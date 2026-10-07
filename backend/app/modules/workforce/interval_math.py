"""Exact streaming half-open interval arithmetic for source-grounded measures."""
def microseconds(start, end):
    delta = end-start
    return (delta.days*86400+delta.seconds)*1000000+delta.microseconds


def union_intervals(intervals):
    """Merge sorted positive intervals; retain only the current union range."""
    first = last = None
    previous = None
    for start, end in intervals:
        if end <= start:
            raise ValueError("A positive source interval is required")
        if previous is not None and start < previous:
            raise ValueError("Source intervals must be ordered")
        previous = start
        if first is None:
            first, last = start, end
        elif start <= last:
            last = max(last, end)
        else:
            yield first, last
            first, last = start, end
    if first is not None:
        yield first, last


def intersection_duration(left, right):
    """Intersect two sorted disjoint unions without materializing either."""
    left, right = iter(left), iter(right)
    a, b = next(left, None), next(right, None)
    total = 0
    while a is not None and b is not None:
        start, end = max(a[0], b[0]), min(a[1], b[1])
        if end > start:
            total += microseconds(start, end)
        if a[1] <= b[1]:
            a = next(left, None)
        else:
            b = next(right, None)
    return total
