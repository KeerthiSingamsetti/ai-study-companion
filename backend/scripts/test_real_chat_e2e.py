"""Opt-in real-model end-to-end test; requires configured Groq credentials.

This script boots a real uvicorn server, so it must not be pointed at
``backend/chatbot.db``: the account it registers (``chat_e2e_*``) is a throwaway
verification identity. The spawned server therefore receives a temporary
``DATABASE_URL`` that is deleted with the run.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from uuid import uuid4

from dotenv import dotenv_values
import httpx


BACKEND = Path(__file__).resolve().parents[1]


def test_real_chat_end_to_end():
    env = os.environ.copy()
    env.update({key: value for key, value in dotenv_values(BACKEND / '.env').items() if value is not None})
    # Keep the verification account out of the development database: the server
    # below is started with its own disposable SQLite file.
    scratch_dir = Path(tempfile.mkdtemp(prefix='studymate-chat-e2e-'))
    env['DATABASE_URL'] = f"sqlite:///{scratch_dir / 'chat-e2e.db'}"
    key = env.get('GROQ_QUIZ_API_KEY', '').strip()
    assert key and key not in {'test-key', 'dummy', 'replace_with_your_groq_key'}, (
        'Real chat E2E blocked: GROQ_QUIZ_API_KEY is missing or a placeholder. '
        'Configure a real key in backend/.env or the process environment. '
        'The dummy-key server is not evidence of successful model requests.'
    )
    log_path = BACKEND / 'chat-e2e-startup.log'
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(
            [str(BACKEND / 'venv' / 'Scripts' / 'python.exe'), '-m', 'uvicorn',
             'app.main:app', '--host', '127.0.0.1', '--port', '8001'],
            cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(base_url='http://127.0.0.1:8001', timeout=120, trust_env=False) as client:
                deadline = time.monotonic() + 120
                credentials = {'email': f'chat_e2e_{uuid4().hex}@example.com', 'password': uuid4().hex}
                while True:
                    assert process.poll() is None, f'Backend exited during startup; inspect {log_path}'
                    try:
                        registered = client.post('/auth/register', json={**credentials, 'display_name': 'Chat E2E verification'})
                        break
                    except httpx.ConnectError:
                        assert time.monotonic() < deadline, f'Backend startup timed out; inspect {log_path}'
                        time.sleep(1)
                assert registered.status_code == 201, registered.text
                login = client.post('/auth/login', json=credentials)
                assert login.status_code == 200, login.text
                headers = {'Authorization': f'Bearer {login.json()["access_token"]}'}
                space_id = project_id = None
                try:
                    space = client.post('/spaces', headers=headers, json={'name': 'Chat E2E Space'})
                    assert space.status_code == 201, space.text
                    space_id = space.json()['id']
                    project = client.post('/threads', headers=headers, json={'title': 'Chat E2E Project', 'space_id': space_id})
                    assert project.status_code == 201, project.text
                    project_id = project.json()['id']
                    response = client.post('/chat', headers=headers, json={
                        'thread_id': project_id, 'message': 'Explain photosynthesis in one sentence.', 'stream': False,
                    })
                    assert response.status_code == 200, f'Chat returned {response.status_code}: {response.text}'
                    body = response.json()
                    assert body.get('message') or body.get('response'), f'Chat returned no reply: {body}'
                    assert body.get('thread_id') == project_id, body
                finally:
                    if project_id:
                        client.delete(f'/threads/{project_id}', headers=headers)
                    if space_id:
                        client.delete(f'/spaces/{space_id}', headers=headers)
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            shutil.rmtree(scratch_dir, ignore_errors=True)
