"""Non-model HTTP smoke check through the running Vite development proxy."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from app.main import app  # Loads local configuration without starting model clients.
from app.auth.service import create_access_token
from app.db import crud
from app.db.session import SessionLocal


def main():
    with SessionLocal() as db:
        user = crud.get_user_by_email(db, 'testuser@example.com')
        if user is None:
            raise RuntimeError('Run the auth tests first to create the test fixture user.')
        token = create_access_token(user_id=user.id, role=user.role)
    with httpx.Client(base_url='http://localhost:5173/api', timeout=15, trust_env=False) as client:
        headers = {'Authorization': f'Bearer {token}'}
        space_id = project_id = None
        try:
            for path in ['/auth/me', '/spaces']:
                response = client.get(path, headers=headers)
                assert response.status_code == 200, (path, response.status_code)
                print(f'GET {path}: 200')
            response = client.post('/spaces', headers=headers, json={'name': 'HTTP verification (temporary)'})
            assert response.status_code == 201, response.text
            space_id = response.json()['id']
            print('POST /spaces: 201')
            response = client.post('/threads', headers=headers, json={'title': 'HTTP project verification', 'space_id': space_id})
            assert response.status_code == 201, response.text
            project_id = response.json()['id']
            print('POST /threads: 201')
            response = client.get('/threads', headers=headers, params={'space_id': space_id})
            assert response.status_code == 200
            assert [row['id'] for row in response.json()] == [project_id]
            print('GET /threads?space_id=selected: 200, correct project only')
            for suffix in ['messages', 'documents']:
                response = client.get(f'/threads/{project_id}/{suffix}', headers=headers)
                assert response.status_code == 200, response.text
                print(f'GET /threads/selected/{suffix}: 200')
        finally:
            if project_id:
                client.delete(f'/threads/{project_id}', headers=headers).raise_for_status()
            if space_id:
                client.delete(f'/spaces/{space_id}', headers=headers).raise_for_status()
            print('Temporary Space and Project removed.')


if __name__ == '__main__':
    main()
