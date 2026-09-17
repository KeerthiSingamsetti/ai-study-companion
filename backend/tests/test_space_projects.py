"""Regression tests for explicit Space -> Project creation and filtering."""

from uuid import uuid4

from app.auth.service import create_access_token
from app.db import crud
from app.db.session import SessionLocal
from app.main import app
from app.services.thread_service import ThreadService


def test_project_creation_and_space_filter(test_client, auth_headers):
    app.state.thread_service = ThreadService()
    spaces = [test_client.post('/spaces', headers=auth_headers, json={'name': f'Space {uuid4()}'}).json() for _ in range(2)]
    created = []
    for space in spaces:
        response = test_client.post('/threads', headers=auth_headers, json={'title': '  Biology  project ', 'space_id': space['id']})
        assert response.status_code == 201, response.text
        project = response.json()
        assert project['space_id'] == space['id']
        assert project['title'] == 'Biology project'
        created.append(project)
    response = test_client.get('/threads', headers=auth_headers, params={'space_id': spaces[0]['id']})
    assert response.status_code == 200
    assert [project['id'] for project in response.json()] == [created[0]['id']]


def test_project_requires_owned_space(test_client, auth_headers):
    app.state.thread_service = ThreadService()
    db = SessionLocal()
    try:
        user_id = str(uuid4())
        crud.create_user(db, user_id=user_id, email=f'{user_id}@example.com', hashed_password='not-a-login', display_name='Other student', role='student')
        space = crud.create_space(db, space_id=str(uuid4()), user_id=user_id, name='Private')
        space_id = space.id
    finally:
        db.close()
    for target in [space_id, str(uuid4())]:
        assert test_client.post('/threads', headers=auth_headers, json={'title': 'Forbidden', 'space_id': target}).status_code == 404
        assert test_client.get('/threads', headers=auth_headers, params={'space_id': target}).status_code == 404
    own_headers = {'Authorization': f'Bearer {create_access_token(user_id=user_id, role="student")}'}
    assert test_client.post('/threads', headers=own_headers, json={'title': 'Allowed', 'space_id': space_id}).status_code == 201


def test_project_requires_auth_and_nonblank_title(test_client, auth_headers):
    assert test_client.post('/threads', json={'title': 'Project', 'space_id': 'missing'}).status_code == 401
    space = test_client.post('/spaces', headers=auth_headers, json={'name': 'Validation'}).json()
    assert test_client.post('/threads', headers=auth_headers, json={'title': '   ', 'space_id': space['id']}).status_code == 422
