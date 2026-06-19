"""One-time 3-legged OAuth (oob/PIN). Run: python -m fatsecret_telegram_bridge.auth_setup

Prints the tokens to put into .env as
FATSECRET_ACCESS_TOKEN / FATSECRET_ACCESS_SECRET.
"""
import os


def exchange_verifier(fs, verifier: str):
    """Exchange a PIN/verifier for (access_token, access_secret)."""
    return fs.authenticate(verifier)


def main() -> None:
    from dotenv import load_dotenv
    from fatsecret import Fatsecret

    load_dotenv()
    key = os.environ["FATSECRET_CONSUMER_KEY"]
    secret = os.environ["FATSECRET_CONSUMER_SECRET"]
    fs = Fatsecret(key, secret)

    url = fs.get_authorize_url(callback_url="oob")
    print("1) Open this link and approve access:\n   " + url)
    verifier = input("2) Paste the PIN/verifier and press Enter: ").strip()

    token, token_secret = exchange_verifier(fs, verifier)
    print("\nDone. Add to .env:")
    print(f"FATSECRET_ACCESS_TOKEN={token}")
    print(f"FATSECRET_ACCESS_SECRET={token_secret}")


if __name__ == "__main__":
    main()
