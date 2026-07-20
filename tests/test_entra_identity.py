from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pytest

from api.identity import EntraTokenValidator, TokenValidationError


TENANT_ID = "11111111-2222-3333-4444-555555555555"
API_CLIENT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
WEB_CLIENT_ID = "99999999-8888-7777-6666-555555555555"
AUTHORITY = "https://freshsense.ciamlogin.com/11111111-2222-3333-4444-555555555555"
ISSUER = f"{AUTHORITY}/v2.0"


class _JwkClient:
    def __init__(self, _url, **_kwargs):
        self.key = None

    def get_jwk_set(self):
        return {"keys": []}

    def get_signing_key_from_jwt(self, _token):
        return SimpleNamespace(key=self.key)


def _validator(public_key):
    client = _JwkClient("unused")
    client.key = public_key

    def factory(_url, **_kwargs):
        return client

    validator = EntraTokenValidator(
        authority=AUTHORITY,
        tenant_id=TENANT_ID,
        audience=API_CLIENT_ID,
        required_scopes=("access_as_user",),
        allowed_client_ids=(WEB_CLIENT_ID,),
        metadata_loader=lambda _url, timeout: {
            "issuer": ISSUER,
            "jwks_uri": "https://freshsense.ciamlogin.com/discovery/keys",
        },
        jwk_client_factory=factory,
    )
    validator.initialize()
    return validator


def _token(private_key, **overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "external-user-subject",
        "tid": TENANT_ID,
        "aud": API_CLIENT_ID,
        "iss": ISSUER,
        "iat": now,
        "exp": now + timedelta(minutes=10),
        "scp": "access_as_user",
        "azp": WEB_CLIENT_ID,
        "name": "Produce Manager",
        "emails": ["manager@example.test"],
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test"})


def test_entra_validator_checks_signature_issuer_audience_tenant_scope_and_client():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    validator = _validator(private_key.public_key())

    claims = validator.validate(_token(private_key))

    assert claims["sub"] == "external-user-subject"
    assert claims["scp"] == "access_as_user"


@pytest.mark.parametrize(
    "overrides",
    [
        {"tid": "another-tenant"},
        {"scp": "profile.read"},
        {"azp": "another-client"},
        {"aud": "another-api"},
        {"iss": "https://issuer.invalid/v2.0"},
    ],
)
def test_entra_validator_rejects_wrong_security_boundary(overrides):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    validator = _validator(private_key.public_key())

    with pytest.raises(TokenValidationError):
        validator.validate(_token(private_key, **overrides))


def test_entra_validator_fails_closed_on_insecure_or_missing_configuration():
    with pytest.raises(TokenValidationError, match="HTTPS"):
        EntraTokenValidator(
            authority="http://identity.example",
            tenant_id=TENANT_ID,
            audience=API_CLIENT_ID,
            required_scopes=("access_as_user",),
        )
    with pytest.raises(TokenValidationError, match="scope"):
        EntraTokenValidator(
            authority=AUTHORITY,
            tenant_id=TENANT_ID,
            audience=API_CLIENT_ID,
            required_scopes=(),
        )
