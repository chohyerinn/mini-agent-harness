def binary_search(arr, target):
    low, high = 0, len(arr) - 1
    while low < high:
        # BUG: low == high로 좁혀진 마지막 후보를 확인하지 않고 종료된다
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
