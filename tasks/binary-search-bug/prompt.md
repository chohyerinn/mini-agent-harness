# 과제: binary_search 경계값 버그 수정

`search_utils.py`의 `binary_search(arr, target)`는 정렬된 리스트 `arr`에서
`target`의 인덱스를 반환하고, 없으면 `-1`을 반환해야 합니다.

현재 구현은 탐색 구간이 원소 한 개로 줄어들었을 때 그 원소를 확인하지 않고
끝나 버리는 off-by-one 버그가 있습니다. 이를 수정하세요.

테스트는 `tests/`에 있습니다. 모든 테스트를 통과시키세요.
