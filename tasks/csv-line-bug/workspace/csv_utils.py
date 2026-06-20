def parse_csv_line(line):
    # BUG: 인용부호로 감싼 필드 안의 쉼표까지 구분자로 취급해 필드를 잘못 나눈다
    return line.split(",")
