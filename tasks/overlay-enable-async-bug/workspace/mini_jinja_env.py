class Environment:
    def __init__(self, enable_async=False):
        self.is_async = bool(enable_async)

    def overlay(self, enable_async=False):
        # BUG: enable_async를 넘기지 않아도 False로 덮어써 버린다.
        return Environment(enable_async=enable_async)
