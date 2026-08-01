from pathlib import Path

import pytest

from zhiming_life.desktop_api.database import Database, NotFoundError


def birth() -> dict:
    return {
        "calendar": "solar",
        "year": 1990,
        "month": 6,
        "day": 15,
        "hour": 14,
        "gender": "male",
    }


def test_person_round_trip_survives_database_reopen(tmp_path: Path):
    db = Database(tmp_path)
    created = db.create_person(
        name="我自己",
        relationship="self",
        birth=birth(),
        notes="互联网",
        person_id="person-self",
    )

    reopened = Database(tmp_path)
    loaded = reopened.get_person(created["id"])

    assert loaded["id"] == "person-self"
    assert loaded["name"] == "我自己"
    assert loaded["birth"] == birth()
    assert loaded["notes"] == "互联网"


def test_update_person_changes_only_supplied_fields(tmp_path: Path):
    db = Database(tmp_path)
    created = db.create_person(name="母亲", relationship="family", birth=birth())

    updated = db.update_person(created["id"], name="妈妈", notes="退休教师")

    assert updated["name"] == "妈妈"
    assert updated["notes"] == "退休教师"
    assert updated["relationship"] == "family"
    assert updated["birth"] == birth()


def test_session_messages_are_scoped_and_persisted(tmp_path: Path):
    db = Database(tmp_path)
    first = db.create_person(name="我", relationship="self", birth=birth())
    second = db.create_person(name="朋友", relationship="friend", birth=birth())
    session = db.create_session(
        primary_person_id=first["id"],
        secondary_person_id=second["id"],
        title="一起看合作",
        session_id="session-1",
    )
    db.add_message(session["id"], "user", "我们适合一起合作吗？")
    db.add_message(session["id"], "assistant", "先看双方命造。")

    reopened = Database(tmp_path)

    assert [item["id"] for item in reopened.list_sessions(first["id"])] == ["session-1"]
    assert [item["id"] for item in reopened.list_sessions(second["id"])] == ["session-1"]
    assert [item["role"] for item in reopened.list_messages("session-1")] == [
        "user",
        "assistant",
    ]


def test_deleting_person_cascades_owned_sessions(tmp_path: Path):
    db = Database(tmp_path)
    person = db.create_person(name="旧卷", relationship="other")
    session = db.create_session(primary_person_id=person["id"], title="旧问")
    db.add_message(session["id"], "user", "旧事")

    db.delete_person(person["id"])

    with pytest.raises(NotFoundError):
        db.get_person(person["id"])
    assert db.list_sessions() == []


def test_unknown_parent_and_invalid_message_role_are_rejected(tmp_path: Path):
    db = Database(tmp_path)

    with pytest.raises(NotFoundError):
        db.create_session(primary_person_id="missing", title="不存在")

    person = db.create_person(name="我", relationship="self")
    session = db.create_session(primary_person_id=person["id"], title="测试")
    with pytest.raises(ValueError, match="role"):
        db.add_message(session["id"], "tool", "不支持")
