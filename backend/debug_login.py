import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate

U = get_user_model()

print("=== ALL USERS ===")
for u in U.objects.all():
    print(f'username={u.username}')
    print(f'  is_active={u.is_active}')
    print(f'  is_staff={u.is_staff}')
    print(f'  is_superuser={u.is_superuser}')
    print(f'  last_login={u.last_login}')
    print(f'  password hash: {u.password[:50]}...')
    print(f'  groups: {list(u.groups.values_list("name", flat=True))}')
    print(f'  user_permissions: {list(u.user_permissions.values_list("codename", flat=True))}')

print("\n=== CHECK PASSWORD ===")
for u in U.objects.filter(username='Misbah'):
    result = u.check_password('Correct-Horse-42!')
    print(f'Misbah check_password("Correct-Horse-42!"): {result}')

print("\n=== AUTHENTICATE ===")
user = authenticate(username='Misbah', password='Correct-Horse-42!')
print(f'authenticate("Misbah", "Correct-Horse-42!"): {user}')

print("\n=== SETTINGS ===")
from django.conf import settings
print(f'AUTH_USER_MODEL: {settings.AUTH_USER_MODEL}')
print(f'AUTHENTICATION_BACKENDS: {settings.AUTHENTICATION_BACKENDS}')