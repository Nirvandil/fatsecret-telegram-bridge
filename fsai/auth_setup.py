"""Разовый 3-legged OAuth (oob/PIN). Запуск: python -m fsai.auth_setup

Печатает токены, которые нужно положить в .env как
FATSECRET_ACCESS_TOKEN / FATSECRET_ACCESS_SECRET.
"""
import os


def exchange_verifier(fs, verifier: str):
    """Обменивает PIN/verifier на (access_token, access_secret)."""
    return fs.authenticate(verifier)


def main() -> None:
    from dotenv import load_dotenv
    from fatsecret import Fatsecret

    load_dotenv()
    key = os.environ["FATSECRET_CONSUMER_KEY"]
    secret = os.environ["FATSECRET_CONSUMER_SECRET"]
    fs = Fatsecret(key, secret)

    url = fs.get_authorize_url(callback_url="oob")
    print("1) Открой ссылку и подтверди доступ:\n   " + url)
    verifier = input("2) Вставь PIN/verifier и нажми Enter: ").strip()

    token, token_secret = exchange_verifier(fs, verifier)
    print("\nГотово. Добавь в .env:")
    print(f"FATSECRET_ACCESS_TOKEN={token}")
    print(f"FATSECRET_ACCESS_SECRET={token_secret}")


if __name__ == "__main__":
    main()
