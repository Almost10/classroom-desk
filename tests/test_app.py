"""Offline integration checks: no Google, Gemini, SMTP, or cloud calls are made."""
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
import zipfile

TEMP=tempfile.TemporaryDirectory()
os.environ.update(APP_SECRET='test-secret-for-offline-checks-only-1234567890',APP_PASSWORD='test-password-12345',DATA_DIR=TEMP.name,BASE_URL='http://testserver',DEMO_MODE='false',GOOGLE_CLIENT_ID='test-client',GOOGLE_CLIENT_SECRET='test-secret',GEMINI_API_KEY='')
from backend.app import db,config,worker
from backend.app.documents import Draft,Section,Slide,Calculation,calculate,render,extract
from backend.app.google import IntegrationError
from backend.app.main import app
from fastapi.testclient import TestClient

class Core(unittest.TestCase):
    def setUp(self):
        db.init()
        with db.connect() as c:
            for table in ('assignments','courses','notifications','settings'): c.execute('DELETE FROM '+table)
        db.init()

    def test_encrypted_secrets_and_restart(self):
        db.save_secret('test',{'token':'not-plaintext'})
        self.assertNotIn('not-plaintext',db.get('test'))
        self.assertEqual(db.secret('test'),{'token':'not-plaintext'})
        with db.connect() as c:
            c.execute("INSERT INTO assignments(id,course_id,title,revision,status,created,updated) VALUES('a','c','A','r','processing',1,1)")
        db.init()
        with db.connect() as c:self.assertEqual(c.execute('SELECT status FROM assignments').fetchone()[0],'queued')

    def test_safe_calculations(self):
        self.assertEqual(calculate('10000 / (1.08 ** 3)'),'7938.3224102017')
        self.assertEqual(calculate('0.1 + 0.2'),'0.3')
        for malicious in ['__import__("os").system("id")','x+1','2**10000','(1).__class__','1/0']:
            with self.assertRaises(Exception): calculate(malicious)

    def test_documents_and_schema(self):
        draft=Draft(title='Finance report',summary='A sample report',formats=['docx','pptx'],sections=[Section(heading='Results',paragraphs=['Present value is 7,938.32.'])],slides=[Slide(title='Present value',bullets=['Discount future cash flows.'])],calculations=[Calculation(label='PV',expression='10000 / (1.08 ** 3)')])
        with tempfile.TemporaryDirectory() as folder:
            files=render(draft,Path(folder))
            self.assertEqual(len(files),2)
            for item in files:
                path=Path(folder)/item['name']
                with zipfile.ZipFile(path) as z:self.assertIsNone(z.testzip())
                mime='application/vnd.openxmlformats-officedocument.'+('wordprocessingml.document' if item['kind']=='DOCX' else 'presentationml.presentation')
                self.assertIn('Present value',extract(path.name,mime,path.read_bytes()))
        self.assertNotIn('$ref',json.dumps(worker.gemini_schema()))
        self.assertNotIn('$defs',json.dumps(worker.gemini_schema()))

    def test_automatic_sync_and_generation(self):
        future=(datetime.now(timezone.utc)+timedelta(days=3)).date()
        work={'id':'work','title':'Finance report','description':'Explain present value. Create a Word document.','creationTime':datetime.now(timezone.utc).isoformat(),'dueDate':{'year':future.year,'month':future.month,'day':future.day},'materials':[],'workType':'ASSIGNMENT'}
        class FakeGoogle:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def courses(self):return [{'id':'course','name':'Finance'}]
            def coursework(self,id):return [work]
            def submissions(self,id):return {'work':'NEW'}
        draft=Draft(title='Finance report',summary='Present value',sections=[Section(heading='Explanation',paragraphs=['Discounting accounts for the time value of money.'])])
        class Response:
            status_code=200
            def json(self):return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':draft.model_dump_json()}]}}]}
        class FakeClient:
            def __init__(self,*args,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def post(self,*args,**kwargs):return Response()
        with patch.object(worker,'Google',FakeGoogle):
            worker.sync()
            with db.connect() as c:c.execute("UPDATE courses SET selected=1")
            worker.sync();worker.sync()
            with db.connect() as c:
                self.assertEqual(c.execute('SELECT count(*) FROM assignments').fetchone()[0],1)
                self.assertEqual(c.execute('SELECT status FROM assignments').fetchone()[0],'queued')
                self.assertEqual(c.execute("SELECT count(*) FROM notifications WHERE kind='new'").fetchone()[0],1)
            db.save_secret('gemini_key','test-key')
            with patch.object(worker.httpx,'Client',FakeClient):worker.process_next()
            with db.connect() as c:row=db.assignment(c.execute('SELECT * FROM assignments').fetchone())
            self.assertEqual(row['status'],'ready')
            self.assertTrue((config.DATA/'files'/row['files'][0]['path']).is_file())
            work['description']='Updated instructions'
            worker.sync()
            with db.connect() as c:self.assertEqual(c.execute('SELECT status FROM assignments').fetchone()[0],'queued')
            class Submitted(FakeGoogle):
                def submissions(self,id):return {'work':'TURNED_IN'}
            with patch.object(worker,'Google',Submitted):worker.sync()
            with db.connect() as c:self.assertEqual(c.execute('SELECT status FROM assignments').fetchone()[0],'skipped')

    def test_transient_failure_is_queued(self):
        with db.connect() as c:
            c.execute("INSERT INTO courses(id,name,selected) VALUES('c','Class',1)")
            c.execute("INSERT INTO assignments(id,course_id,title,revision,status,created,updated) VALUES('a','c','A','r','queued',1,1)")
        with patch.object(worker,'draft_assignment',side_effect=IntegrationError('quota',retry=True,quota=True)):worker.process_next()
        with db.connect() as c:row=c.execute('SELECT * FROM assignments').fetchone()
        self.assertEqual(row['status'],'queued');self.assertEqual(row['attempts'],1)
        self.assertGreater(row['available_at'],0)

    def test_auth_and_csrf(self):
        with patch.object(worker,'run',new=idle_worker):
            with TestClient(app) as client:
                self.assertEqual(client.get('/api/dashboard').status_code,401)
                self.assertEqual(client.post('/api/login',json={'password':config.PASSWORD}).status_code,403)
                headers={'X-Desk-Request':'1','Origin':config.BASE_URL}
                self.assertEqual(client.post('/api/login',json={'password':config.PASSWORD},headers=headers).status_code,200)
                self.assertEqual(client.get('/api/dashboard').status_code,200)
                self.assertEqual(client.post('/api/check',headers={**headers,'Origin':'https://evil.example'}).status_code,403)
                self.assertEqual(client.get('/api/assignments/missing/files/secret').status_code,404)
                self.assertEqual(client.post('/api/logout',headers=headers).status_code,200)
                self.assertEqual(client.get('/api/settings').status_code,401)

async def idle_worker():
    import asyncio
    await asyncio.Event().wait()

if __name__=='__main__':unittest.main()
