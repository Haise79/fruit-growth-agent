from pydantic import EmailStr, TypeAdapter

from fruit_agent.demo.constants import DEMO_EMAILS


def test_demo_member_emails_are_api_serializable() -> None:
    adapter = TypeAdapter(EmailStr)

    assert len(DEMO_EMAILS) == 4
    for email in DEMO_EMAILS.values():
        assert str(adapter.validate_python(email)) == email
