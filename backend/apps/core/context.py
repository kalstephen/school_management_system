"""Per-request context: the acting user and the active school.

Set by SchoolContextMiddleware so model code (audit columns, audit log) can find who is
acting without passing the request around.
"""

from contextvars import ContextVar

_current_user = ContextVar("current_user", default=None)
_current_school = ContextVar("current_school", default=None)
_platform_session = ContextVar("platform_session", default=False)


def get_platform_session():
    return _platform_session.get()


def set_platform_session(value):
    return _platform_session.set(bool(value))


def reset_platform_session(token):
    _platform_session.reset(token)


def get_current_user():
    return _current_user.get()


def get_current_school():
    return _current_school.get()


def set_context(user, school):
    return _current_user.set(user), _current_school.set(school)


def reset_context(tokens):
    user_token, school_token = tokens
    _current_user.reset(user_token)
    _current_school.reset(school_token)


class acting_as:
    """Context manager for code outside a request (commands, tests)."""

    def __init__(self, user=None, school=None):
        self.user, self.school = user, school

    def __enter__(self):
        self.tokens = set_context(self.user, self.school)
        return self

    def __exit__(self, *exc):
        reset_context(self.tokens)
