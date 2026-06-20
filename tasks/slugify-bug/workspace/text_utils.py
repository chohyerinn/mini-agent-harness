def slugify(text):
    # BUG: 소문자 변환/기호 제거/하이픈 정리가 빠져 있음
    return text.replace(" ", "-")
