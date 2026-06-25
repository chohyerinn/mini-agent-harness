_missing = object()


class Environment:
    def __init__(self, enable_async=False):
        self.is_async = bool(enable_async)

    def overlay(self, enable_async=_missing):
        if enable_async is _missing:
            enable_async = self.is_async
        return Environment(enable_async=enable_async)
