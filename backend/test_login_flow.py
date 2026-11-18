import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()

from django.conf import settings
settings.ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

from django.test import Client
from django.contrib.auth import authenticate

# Test 1: Direct authenticate
print("=== Test 1: Direct authenticate ===")
user = authenticate(username='Misbah', password='Correct-Horse-42!')
print(f"authenticate result: {user}")

# Test 2: Django test client
print("\n=== Test 2: Django test client ===")
client = Client()
response = client.post(
    '/api/v1/auth/login/',
    data='{"username": "Misbah", "password": "Correct-Horse-42!"}',
    content_type='application/json'
)
print(f"Status: {response.status_code}")
try:
    print(f"Response: {response.json()}")
except:
    print(f"Response text: {response.content[:500]}")

# Test 3: With CSRF enforcement
print("\n=== Test 3: Django test client with CSRF ===")
client = Client(enforce_csrf_checks=True)
response = client.post(
    '/api/v1/auth/login/',
    data='{"username": "Misbah", "password": "Correct-Horse-42!"}',
    content_type='application/json'
)
print(f"Status: {response.status_code}")
try:
    print(f"Response: {response.json()}")
except:
    print(f"Response text: {response.content[:500]}")

# Test 4: Check throttle for this specific username
print("\n=== Test 4: Check throttle directly ===")
from accounts.throttling import check_login_throttle
from django.utils import timezone
decision = check_login_throttle('Misbah', '127.0.0.1')
print(f"Throttle decision for Misbah/127.0.0.1: allowed={decision.allowed}, retry_after={decision.retry_after_seconds}")

# Test 5: Check with different IP
decision = check_login_throttle('Misbah', '192.168.1.1')
print(f"Throttle decision for Misbah/192.168.1.1: allowed={decision.allowed}, retry_after={decision.retry_after_seconds}")

# Test 6: Full login view flow
print("\n=== Test 6: Full login view flow ===")
from accounts.views import LoginView
from rest_framework.request import Request
from django.http import HttpRequest

# Create a mock request
request = HttpRequest()
request.method = 'POST'
request.META['CONTENT_TYPE'] = 'application/json'
request._body = b'{"username": "Misbah", "password": "Correct-Horse-42!"}'
request.META['REMOTE_ADDR'] = '127.0.0.1'

drf_request = Request(request)

# Check serializer
from accounts.serializers import LoginSerializer
import json
serializer = LoginSerializer(data=json.loads(request.body.decode()))
print(f"Serializer valid: {serializer.is_valid()}")
if serializer.is_valid():
    print(f"Validated data: {serializer.validated_data}")
else:
    print(f"Errors: {serializer.errors}")

# Test 7: Check authenticate with request
print("\n=== Test 7: Authenticate with request ===")
user = authenticate(request=request, username='Misbah', password='Correct-Horse-42!')
print(f"authenticate with request: {user}")

# Test 8: Simulate actual view logic
print("\n=== Test 8: Simulate view logic ===")
from accounts.throttling import check_login_throttle
from django.contrib.auth import authenticate
from accounts.tokens import create_auth_session
from rest_framework.request import Request
from django.http import HttpRequest

request = HttpRequest()
request.method = 'POST'
request.META['CONTENT_TYPE'] = 'application/json'
request._body = b'{"username": "Misbah", "password": "Correct-Horse-42!"}'
request.META['REMOTE_ADDR'] = '127.0.0.1'

# Get client IP
from core.security import get_client_ip
client_ip = get_client_ip(request)
print(f"Client IP: {client_ip}")

# Check throttle
decision = check_login_throttle('Misbah', client_ip)
print(f"Throttle: allowed={decision.allowed}, retry_after={decision.retry_after_seconds}")

if decision.allowed:
    user = authenticate(request, username='Misbah', password='Correct-Horse-42!')
    print(f"Authenticate result: {user}")
    if user is not None and user.is_active:
        print(f"User active: {user.is_active}")
        print("SUCCESS - would create auth session")
    else:
        print(f"FAIL - user=None or not active: {user}")
else:
    print(f"THROTTLED - retry_after={decision.retry_after_seconds}")