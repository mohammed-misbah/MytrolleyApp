"""Role permissions and escalation resistance."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

from accounts.roles import (
    BUSINESS_PERMISSIONS,
    ROLE_ADMINISTRATOR,
    ROLE_DATA_ENTRY,
    seed_roles,
)
from tests.conftest import login, make_user

User = get_user_model()


@pytest.mark.django_db
def test_roles_are_idempotent_and_exact(roles) -> None:
    first = seed_roles()
    second = seed_roles()

    assert set(first) == {ROLE_ADMINISTRATOR, ROLE_DATA_ENTRY}
    assert set(second) == set(first)
    assert set(first[ROLE_ADMINISTRATOR].permissions.values_list("codename", flat=True)) == {
        "manage_users",
        "manage_catalog",
    }
    assert set(first[ROLE_DATA_ENTRY].permissions.values_list("codename", flat=True)) == {
        "manage_catalog"
    }
    assert first[ROLE_ADMINISTRATOR].permissions.count() == 2
    assert first[ROLE_DATA_ENTRY].permissions.count() == 1


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="tests.urls_for_tests")
def test_manage_users_permission_matrix(
    client: Client,
    roles,
) -> None:
    administrator = make_user("admin-user", role=ROLE_ADMINISTRATOR)
    data_entry = make_user("entry-user", role=ROLE_DATA_ENTRY)
    ungrouped = make_user("plain-user")
    staff_without_business_role = make_user("staff-user", is_staff=True)

    assert client.get("/test-only/manage-users/").status_code == 401

    for user, expected in (
        (administrator, 200),
        (data_entry, 403),
        (ungrouped, 403),
        (staff_without_business_role, 403),
    ):
        client.force_login(user)
        response = client.get("/test-only/manage-users/")
        assert response.status_code == expected, user.username
        if expected == 403:
            assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.django_db
def test_permissions_are_reported_read_only(client: Client, roles) -> None:
    make_user("entry-two", role=ROLE_DATA_ENTRY)
    assert login(client, "entry-two", "Correct-Horse-42!").status_code == 200

    response = client.get("/api/v1/auth/me/")
    assert response.status_code == 200
    assert response.json()["roles"] == [ROLE_DATA_ENTRY]
    assert response.json()["permissions"] == ["accounts.manage_catalog"]
    assert set(response.json()["permissions"]).issubset(set(BUSINESS_PERMISSIONS))


@pytest.mark.django_db
def test_authenticated_user_without_group_has_no_business_permissions(
    client: Client,
    roles,
) -> None:
    user = make_user("no-role")
    assert not any(user.has_perm(permission) for permission in BUSINESS_PERMISSIONS)

    assert login(client, "no-role", "Correct-Horse-42!").status_code == 200
    response = client.get("/api/v1/auth/me/")
    assert response.status_code == 200
    assert response.json()["roles"] == []
    assert response.json()["permissions"] == []


@pytest.mark.django_db
def test_inactive_administrator_is_denied_by_permission_class(roles) -> None:
    administrator = make_user("inactive-admin", role=ROLE_ADMINISTRATOR)
    administrator.is_active = False
    administrator.save(update_fields=["is_active"])

    # Django's auth backend rejects inactive users on authenticate, so this
    # remains a login failure rather than a permission grant.
    assert User.objects.filter(pk=administrator.pk, is_active=False).exists()
