"""Command-line helpers for the web version.

python -m bejitech.web genkey   print a new encryption key and a new cookie secret
python -m bejitech.web serve    run the web server locally (http://127.0.0.1:8000)
python -m bejitech.web reset-two-step USERNAME
                                turn off two-step login for a user who lost their phone; they set it up
                                again at their next sign-in (run it from the Render "Shell" tab)
"""
from __future__ import annotations

import base64
import os
import secrets
import sys


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "help"
    if cmd == "genkey":
        print("BEJITECH_DEK=" + base64.b64encode(os.urandom(32)).decode())
        print("BEJITECH_SECRET_KEY=" + secrets.token_urlsafe(48))
        print("BEJITECH_SETUP_TOKEN=" + secrets.token_urlsafe(12))
        return 0
    if cmd == "serve":
        import uvicorn
        uvicorn.run("bejitech.web.main:create_app", factory=True, host=os.environ.get("HOST", "127.0.0.1"),
                    port=int(os.environ.get("PORT", "8000")), proxy_headers=True, forwarded_allow_ips="*")
        return 0
    if cmd == "reset-two-step" and len(argv) > 2:
        from sqlalchemy import select

        from bejitech.db.models import User
        from bejitech.services.common import audit
        from bejitech.web.config import WebConfig
        from bejitech.web.main import WebState

        state = WebState(WebConfig.from_env())
        with state.db.session() as s:
            user = s.scalar(select(User).where(User.username == argv[2].strip().lower()))
            if not user:
                print(f"No user called {argv[2]!r}.")
                return 1
            user.totp_secret = user.totp_nonce = None
            user.totp_last_step = 0
            user.failed_logins = 0
            user.locked_until = None
            audit(s, user.id, "TWO_STEP_RESET", "user", user.uuid, via="command line")
        print(f"Two-step login reset for {user.username}. Set it up again at the next sign-in.")
        return 0
    print(__doc__)
    return 0 if cmd == "help" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
