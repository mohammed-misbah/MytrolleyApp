import requests
import json

base = 'http://127.0.0.1:8000'

# 1. Test CSRF endpoint returns 404
print('=== 1. CSRF endpoint (should be 404) ===')
r = requests.get(f'{base}/api/v1/auth/csrf/')
print(f'Status: {r.status_code}')
try:
    print(f'Response: {r.json()}')
except:
    print(f'Response (non-JSON): {r.text[:200]}')

# 2. Login
print('\n=== 2. Login ===')
r = requests.post(f'{base}/api/v1/auth/login/', json={'username': 'Misbah', 'password': 'Correct-Horse-42!'}, headers={'Content-Type': 'application/json'})
print(f'Status: {r.status_code}')
print(f'Response: {json.dumps(r.json(), indent=2)}')
print(f'Cookies: {dict(r.cookies)}')
access_token = r.json().get('access')
csrf_cookie = r.cookies.get('csrftoken')
refresh_cookie = r.cookies.get('refresh_token')
print(f'csrftoken cookie: {csrf_cookie}')
print(f'refresh_token cookie: {refresh_cookie}')

# 3. Test /me/ with access token
print('\n=== 3. /me/ with access token ===')
headers = {'Authorization': f'Bearer {access_token}'}
r = requests.get(f'{base}/api/v1/auth/me/', headers=headers)
print(f'Status: {r.status_code}')
print(f'Response: {json.dumps(r.json(), indent=2)}')

# 4. Test refresh with cookie + CSRF
print('\n=== 4. Refresh with cookie + CSRF ===')
r = requests.post(f'{base}/api/v1/auth/refresh/', json={}, headers={'Content-Type': 'application/json', 'X-CSRFToken': csrf_cookie}, cookies={'refresh_token': refresh_cookie, 'csrftoken': csrf_cookie})
print(f'Status: {r.status_code}')
print(f'Response: {json.dumps(r.json(), indent=2) if r.status_code == 200 else r.text}')
print(f'New cookies: {dict(r.cookies)}')

# 5. Test logout
print('\n=== 5. Logout ===')
headers = {'Authorization': f'Bearer {access_token}'}
r = requests.post(f'{base}/api/v1/auth/logout/', headers=headers, cookies={'refresh_token': refresh_cookie, 'csrftoken': csrf_cookie})
print(f'Status: {r.status_code}')
print(f'Response: {json.dumps(r.json(), indent=2)}')
print(f'Cookies cleared: {dict(r.cookies)}')

# 6. Test /me/ after logout
print('\n=== 6. /me/ after logout (should be 401) ===')
r = requests.get(f'{base}/api/v1/auth/me/', headers=headers)
print(f'Status: {r.status_code}')
print(f'Response: {json.dumps(r.json(), indent=2)}')

# 7. Test schema
print('\n=== 7. Schema (check CSRF absent) ===')
r = requests.get(f'{base}/api/v1/schema/', headers={'Accept': 'application/json'})
print(f'Status: {r.status_code}')
try:
    schema = r.json()
    paths = schema.get('paths', {})
    print(f'/api/v1/auth/csrf/ in paths: {"/api/v1/auth/csrf/" in paths}')
    print(f'/api/v1/auth/refresh/ in paths: {"/api/v1/auth/refresh/" in paths}')
    print(f'X-CSRFToken in schema: {"X-CSRFToken" in json.dumps(schema)}')
    print(f'jwtAuth security scheme: {"jwtAuth" in schema.get("components", {}).get("securitySchemes", {})}')
except:
    print(f'Response (non-JSON): {r.text[:500]}')

print('\n=== ALL MANUAL CHECKS COMPLETE ===')