"""Print a cryptographically secure local API key without storing it."""

import secrets


def generate_api_key() -> str:
    """Return a new high-entropy key suitable for a local secret file."""
    return secrets.token_urlsafe(32)


if __name__ == "__main__":
    print(generate_api_key())
