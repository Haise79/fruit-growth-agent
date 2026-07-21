from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from fruit_agent.config import Settings
from fruit_agent.demo.auth import demo_enabled, issue_demo_token, jwt_verification_key
from fruit_agent.demo.constants import DEMO_TENANT_ID, DEMO_USERS
from fruit_agent.identity.models import Role


def _demo_settings(tmp_path: Path) -> Settings:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path = tmp_path / "demo-private.pem"
    public_path = tmp_path / "demo-public.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return Settings(
        environment="development",
        demo_mode=True,
        demo_private_key_path=str(private_path),
        demo_public_key_path=str(public_path),
    )


def test_demo_mode_requires_development_and_explicit_switch() -> None:
    assert not demo_enabled(Settings(environment="production", demo_mode=True))
    assert not demo_enabled(Settings(environment="development", demo_mode=False))
    assert demo_enabled(Settings(environment="development", demo_mode=True))


def test_demo_token_contains_only_fixed_identity_and_short_expiry(
    tmp_path: Path,
) -> None:
    settings = _demo_settings(tmp_path)
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)

    session = issue_demo_token(Role.owner, settings, now=now)
    claims = jwt.decode(
        session.access_token,
        Path(settings.demo_public_key_path).read_text(encoding="utf-8"),
        algorithms=["RS256"],
        audience=settings.jwt_audience,
        options={"verify_exp": False, "verify_iat": False},
    )

    assert claims["tenant_id"] == str(DEMO_TENANT_ID)
    assert claims["sub"] == str(DEMO_USERS[Role.owner])
    assert datetime.fromtimestamp(claims["exp"], UTC) == now + timedelta(minutes=30)
    assert set(claims) == {"sub", "tenant_id", "aud", "iat", "exp"}
    assert session.role is Role.owner
    assert session.expires_at == now + timedelta(minutes=30)


def test_demo_token_requires_an_existing_private_key(tmp_path: Path) -> None:
    settings = Settings(
        environment="development",
        demo_mode=True,
        demo_private_key_path=str(tmp_path / "missing.pem"),
    )

    try:
        issue_demo_token(Role.support, settings)
    except FileNotFoundError as exc:
        assert exc.filename == str(tmp_path / "missing.pem")
    else:
        raise AssertionError("missing demo private key must fail closed")


def test_demo_public_key_is_used_only_when_demo_mode_is_enabled(tmp_path: Path) -> None:
    settings = _demo_settings(tmp_path)
    public_key = Path(settings.demo_public_key_path).read_text(encoding="utf-8")

    assert jwt_verification_key(settings) == public_key
    assert jwt_verification_key(
        Settings(
            environment="development",
            demo_mode=True,
            jwt_public_key="configured-production-key",
            demo_public_key_path=settings.demo_public_key_path,
        )
    ) == "configured-production-key"
    assert jwt_verification_key(
        Settings(
            environment="production",
            demo_mode=True,
            demo_public_key_path=settings.demo_public_key_path,
        )
    ) == ""
