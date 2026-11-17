"""Create the first superuser interactively, without command-line passwords."""

from __future__ import annotations

import argparse
import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction

from accounts.roles import ROLE_ADMINISTRATOR, seed_roles

User = get_user_model()


class Command(BaseCommand):
    """Interactive initial administrator provisioning.

    Passwords are read with ``getpass`` and never accepted as arguments, so
    they do not land in shell history or process listings.
    """

    help = (
        "Create an initial superuser in the Administrator group. Prompts for "
        "username, email and password; no defaults or hardcoded credentials."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--username",
            help="Optional username; prompted when omitted.",
        )
        parser.add_argument(
            "--email",
            help="Optional email; prompted when omitted.",
        )

    def handle(self, *args: object, **options: object) -> None:
        username = str(options.get("username") or "").strip()
        email = str(options.get("email") or "").strip()

        if not username:
            username = input("Username: ").strip()
        if not email:
            email = input("Email: ").strip()

        self._validate_username(username)
        if not email:
            raise CommandError("Email is required.")

        password = getpass.getpass("Password: ")
        confirmation = getpass.getpass("Password (again): ")
        if not password:
            raise CommandError("Password must not be empty.")
        if password != confirmation:
            raise CommandError("Passwords do not match.")

        candidate = User(username=username, email=email)
        try:
            validate_password(password, user=candidate)
        except ValidationError as exc:
            # Validation messages never echo the password.
            raise CommandError("Password rejected: " + " ".join(exc.messages)) from exc

        if User.objects.filter(username__iexact=username).exists():
            raise CommandError(
                f"A user with username '{username}' already exists. No account was changed."
            )
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError("A user with that email already exists. No account was changed.")

        seed_roles()
        try:
            with transaction.atomic():
                user = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                )
                administrator = Group.objects.get(name=ROLE_ADMINISTRATOR)
                user.groups.add(administrator)
        except Exception as exc:  # pragma: no cover - database constraint guard
            raise CommandError(
                "The administrator account could not be created; no partial account was kept."
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(f"Created administrator '{username}'. No password was logged.")
        )

    @staticmethod
    def _validate_username(username: str) -> None:
        if not username:
            raise CommandError("Username is required.")
        field = User._meta.get_field(User.USERNAME_FIELD)
        if not isinstance(field, models.Field):
            raise CommandError("Username field configuration is invalid.")
        try:
            field.run_validators(username)
            field.clean(username, None)
        except ValidationError as exc:
            raise CommandError("Invalid username: " + " ".join(exc.messages)) from exc
