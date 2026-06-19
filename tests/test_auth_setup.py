from fatsecret_telegram_bridge.auth_setup import exchange_verifier


class FakeFs:
    def __init__(self):
        self.authed_with = None

    def get_authorize_url(self, callback_url="oob"):
        return "https://auth.example/url"

    def authenticate(self, verifier):
        self.authed_with = verifier
        return ("ACCESS_TOKEN", "ACCESS_SECRET")


def test_exchange_verifier_returns_tokens():
    fs = FakeFs()
    token, secret = exchange_verifier(fs, "1234")
    assert (token, secret) == ("ACCESS_TOKEN", "ACCESS_SECRET")
    assert fs.authed_with == "1234"
