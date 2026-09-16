# envguard test fixture - benign application code

MESSAGE = "nothing secret lives here"


def greet(name: str) -> str:
    """Return a friendly greeting."""
    return f"hello, {name}"