"""Secure one-shot tool: set a new password for an existing user by exact email.

Usage (from backend container or workspace):
    python -m app.scripts.set_password accept@local.test

Features:
- Reuses the app's existing bcrypt password-hashing utility (get_password_hash).
- Prompts for the password securely via getpass; never prints or logs it.
- Updates only the selected user's hashed_password and updated_at in a transaction.
- Refuses to run when APP_ENV=production.
- Does NOT create accounts, change roles, seed records, run migrations,
  modify timetable data, or reset Docker volumes.
- Does NOT execute automatically; it is a strictly manual command.
"""

import os
import sys
from datetime import datetime, timezone
from getpass import getpass

# Production guard BEFORE any app imports that validate settings.
_PRODUCTION = os.getenv("APP_ENV", "development") == "production"


def main() -> None:
    """Synchronous entry point so the script can be run with `python -m`."""
    # Prevent running in production after checking env var.
    if _PRODUCTION:
        print("Error: Refusing to run in production environment.", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) < 2:
        print(
            "Usage: python -m app.scripts.set_password <user-email>",
            file=sys.stderr,
        )
        sys.exit(1)

    email = sys.argv[1]

    # Now import app modules (safe since we already checked production).
    from getpass import getpass  # noqa: E402
    from datetime import timezone  # noqa: E402
    from sqlalchemy import select  # noqa: E402

    from app.core.security import get_password_hash  # noqa: E402
    from app.database.connection import AsyncSessionLocal  # noqa: E402
    from app.database.models.user import User  # noqa: E402

    import asyncio

    async def async_main() -> None:
        password = getpass("Enter new password: ")
        confirm = getpass("Confirm new password: ")

        if password != confirm:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if user is None:
                print(f"Error: No user found with email: {email}", file=sys.stderr)
                sys.exit(1)

            # Reuse the app's existing password-hashing utility.
            user.hashed_password = get_password_hash(password)

            # updated_at is handled by the model's onupdate callback (_utc_now),
            # but we explicitly set it here for transactional guarantee.
            user.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(user)

        print(f"Success: Password updated for user '{email}'.")

    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nOperation cancelled.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
