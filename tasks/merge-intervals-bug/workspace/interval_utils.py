def merge_intervals(intervals):
    # BUG: 입력이 이미 start 기준으로 정렬돼 있다고 가정함
    if not intervals:
        return []
    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        last = merged[-1]
        if start <= last[1]:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])
    return merged
