"""Offline API regression tests for the MY2022 beta5 session fixes.

Run from repository root: python3 -m unittest discover -s tests -p test_beta5_session.py -v
No actual Lynk account, vehicle, network or Home Assistant installation is used.
"""
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "lynkco"
PACKAGE = "test_lynkco_beta5_isolated"


class _HTTPError(Exception):
    pass


class _Response:
    def __init__(self, status, payload=None):
        self.status = status
        self.payload = payload
        self.content_length = 0 if payload is None else 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, **kwargs):
        return self.payload

    async def text(self):
        return ""

    def raise_for_status(self):
        if self.status >= 400:
            raise _HTTPError(str(self.status))


class _Session:
    def __init__(self, responses, *, tokens=(), validations=()):
        self.responses = list(responses)
        self.tokens = list(tokens)
        self.validations = list(validations)
        self.request_count = 0
        self.token_count = 0
        self.validate_count = 0

    def request(self, *args, **kwargs):
        self.request_count += 1
        return _Response(*self.responses.pop(0))

    def post(self, url, **kwargs):
        if "oauth2" in url:
            self.token_count += 1
            return _Response(*self.tokens.pop(0))
        self.validate_count += 1
        return _Response(*self.validations.pop(0))


def _load_api():
    # Import only api.py and its constants. Avoid executing HA integration
    # __init__.py; this suite should work without HA, network and dependencies.
    aiohttp = types.ModuleType("aiohttp")
    class Timeout:
        def __init__(self, *, total):
            self.total = total
    aiohttp.ClientTimeout = Timeout
    aiohttp.ClientResponse = type("ClientResponse", (), {})
    aiohttp.ClientSession = type("ClientSession", (), {})
    aiohttp.ClientError = type("ClientError", (Exception,), {})
    aiohttp.ContentTypeError = type("ContentTypeError", (Exception,), {})

    pkg = types.ModuleType(PACKAGE)
    pkg.__path__ = [str(ROOT)]
    with mock.patch.dict(sys.modules, {"aiohttp": aiohttp, "pkce": types.ModuleType("pkce"), PACKAGE: pkg}):
        const_spec = importlib.util.spec_from_file_location(PACKAGE + ".const", ROOT / "const.py")
        const = importlib.util.module_from_spec(const_spec)
        sys.modules[const_spec.name] = const
        const_spec.loader.exec_module(const)
        api_spec = importlib.util.spec_from_file_location(PACKAGE + ".api", ROOT / "api.py")
        api = importlib.util.module_from_spec(api_spec)
        sys.modules[api_spec.name] = api
        api_spec.loader.exec_module(api)
    return api


class SessionTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_api()

    def _api(self, session):
        with mock.patch.object(self.module.LynkCoAPI, "_update_claims", lambda self: None):
            api = self.module.LynkCoAPI(session, "old-token", "old-refresh", "fake-device")
        api._update_claims = lambda: None
        return api

    async def test_known_403_claims_session_and_retries(self):
        session = _Session(
            [(200, {"ok": 1}), (403, {"error": "session"}), (200, {"ok": 2})],
            validations=[(200, {"valid": True})],
        )
        api = self._api(session)
        self.assertEqual((await api._request("GET", "https://example.test/charge"))["ok"], 1)
        self.assertEqual((await api._request("GET", "https://example.test/charge"))["ok"], 2)
        self.assertEqual(session.validate_count, 1)

    async def test_unknown_403_does_not_claim_phone_session(self):
        session = _Session([(403, {"error": "unsupported"})])
        api = self._api(session)
        with self.assertRaises(_HTTPError):
            await api._request("GET", "https://example.test/unknown")
        self.assertEqual(session.validate_count, 0)
        self.assertEqual(session.token_count, 0)

    async def test_reclaim_is_throttled(self):
        session = _Session(
            [(200, {"ok": True}), (403, {}), (200, {}), (403, {}), (200, {})],
            validations=[(200, {"valid": True})],
        )
        api = self._api(session)
        url = "https://example.test/charge"
        await api._request("GET", url)
        await api._request("GET", url)
        await api._request("GET", url)
        self.assertEqual(session.validate_count, 1)

    async def test_401_refreshes_and_retries_once(self):
        session = _Session(
            [(401, {}), (200, {"updated": True})],
            tokens=[(200, {"access_token": "new-access", "refresh_token": "new-refresh"})],
        )
        api = self._api(session)
        result = await api._request("GET", "https://example.test/battery")
        self.assertTrue(result["updated"])
        self.assertEqual(session.token_count, 1)
        self.assertEqual(api.access_token, "new-access")

    async def test_rejected_token_requests_reauth(self):
        session = _Session([], tokens=[(400, {"error": "invalid_grant"})])
        api = self._api(session)
        with self.assertRaises(self.module.LynkCoAuthError):
            await api.refresh_tokens()

    async def test_rate_limit_is_temporary_not_reauth(self):
        session = _Session([], tokens=[(429, {"error": "too_many_requests"})])
        api = self._api(session)
        with self.assertRaises(self.module.LynkCoTransientError):
            await api.refresh_tokens()

    async def test_concurrent_401_does_not_double_refresh(self):
        session = _Session(
            [(401, {}), (401, {}), (200, {}), (200, {})],
        )
        api = self._api(session)
        runs = 0

        async def refresh_once():
            nonlocal runs
            runs += 1
            await asyncio.sleep(0)  # Let second request observe the original token.
            api._access_token = "fresh-token"
            return True

        api._refresh_tokens_locked = refresh_once
        await asyncio.gather(
            api._request("GET", "https://example.test/a"),
            api._request("GET", "https://example.test/b"),
        )
        self.assertEqual(runs, 1)


if __name__ == "__main__":
    unittest.main()
