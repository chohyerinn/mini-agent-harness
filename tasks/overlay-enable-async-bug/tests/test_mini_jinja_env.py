from mini_jinja_env import Environment


def test_sync_environment_overlay_stays_sync_by_default():
    env = Environment()
    assert env.overlay().is_async is False


def test_sync_environment_can_enable_async_overlay():
    env = Environment()
    assert env.overlay(enable_async=True).is_async is True


def test_async_environment_overlay_keeps_async_by_default():
    env = Environment(enable_async=True)
    assert env.overlay().is_async is True


def test_async_environment_can_disable_async_overlay():
    env = Environment(enable_async=True)
    assert env.overlay(enable_async=False).is_async is False

