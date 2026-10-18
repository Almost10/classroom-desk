import asyncio
import hashlib
import hmac
import json
import mimetypes
import re
import secrets
import shutil
import threading
import time
import uuid
import hashlib
from contextlib import asynccontextmanager,contextmanager
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,urlsplit

import httpx
from fastapi import Depends,FastAPI,File,Form,HTTPException,Request,UploadFile
from fastapi.responses import FileResponse,RedirectResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from starlette.middleware.sessions import SessionMiddleware
from . import config,db,worker

operation_lock=threading.Lock()
# One worker process only. Queue state persists in SQLite.
original_tick=worker.tick

def locked_tick():
    if operation_lock.acquire(blocking=False):
        try: original_tick()
        finally: operation_lock.release()
worker.tick=locked_tick

@contextmanager
def idle_required():
    if not operation_lock.acquire(blocking=False): raise HTTPException(409,'A background task is running. Please try again when it finishes.')
    try: yield
    finally: operation_lock.release()

@asynccontextmanager
async def lifespan(app):
    db.init()
    if config.DEMO:
        from .demo import seed
        seed()
    task=asyncio.create_task(worker.run())
    yield
    task.cancel()
    try: await task
    except asyncio.CancelledError: pass

app=FastAPI(title='Classroom Desk',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(SessionMiddleware,secret_key=config.SECRET,same_site='lax',https_only=config.BASE_URL.startswith('https://'),max_age=86400,session_cookie='desk_session')

def valid_request_origin(origin:str|None)->bool:
    if not origin:
        return True
    expected=urlsplit(config.BASE_URL)
    received=urlsplit(origin)
    if received.scheme.lower()!=expected.scheme.lower() or received.port!=expected.port:
        return False
    if received.netloc.lower()==expected.netloc.lower():
        return True
    # localhost and 127.0.0.1 are interchangeable for this loopback-only app.
    loopback={'localhost','127.0.0.1','::1'}
    return (expected.hostname in loopback and received.hostname in loopback
            and (expected.port or (443 if expected.scheme=='https' else 80))
            == (received.port or (443 if received.scheme=='https' else 80)))

@app.middleware('http')
async def security(request,call_next):
    expected=urlsplit(config.BASE_URL)
    loopback={'localhost','127.0.0.1','::1'}
    if (expected.hostname in loopback and request.url.hostname in loopback
            and request.url.hostname!=expected.hostname):
        # Keep the session cookie on one canonical loopback host throughout
        # OAuth; localhost and 127.0.0.1 have separate browser cookie jars.
        target=request.url.replace(scheme=expected.scheme,netloc=expected.netloc)
        return RedirectResponse(str(target),status_code=307)
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if request.headers.get('x-desk-request')!='1' or not valid_request_origin(origin):
            return JSONResponse({'detail':'Request origin or CSRF header is invalid.'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    if request.url.path.startswith('/api/'): response.headers['Cache-Control']='no-store'
    return response

def authenticated(request:Request):
    if not request.session.get('authenticated'): raise HTTPException(401,'Please sign in.')

class Login(BaseModel): password:str=Field(max_length=200)
login_attempts=[]

@app.post('/api/login')
async def login(body:Login,request:Request):
    now=time.monotonic()
    login_attempts[:]=[x for x in login_attempts if now-x<60]
    if len(login_attempts)>=8: raise HTTPException(429,'Too many sign-in attempts. Wait one minute.')
    login_attempts.append(now)
    if not hmac.compare_digest(hashlib.sha256(body.password.encode()).digest(),hashlib.sha256(config.PASSWORD.encode()).digest()):
        raise HTTPException(401,'Incorrect password.')
    request.session.clear(); request.session['authenticated']=True
    return {'ok':True}

@app.post('/api/logout',dependencies=[Depends(authenticated)])
async def logout(request:Request):
    request.session.clear(); return {'ok':True}

@app.get('/api/session')
async def session(request:Request):
    return {'authenticated':bool(request.session.get('authenticated')),'demo':config.DEMO}

@app.get('/api/dashboard',dependencies=[Depends(authenticated)])
def dashboard():
    with db.connect() as c:
        rows=c.execute('SELECT a.*,coalesce(c.name,\'Archived class\') AS course_name FROM assignments a LEFT JOIN courses c ON c.id=a.course_id ORDER BY a.due IS NULL,a.due,a.created DESC').fetchall()
        notifications=[dict(row) for row in c.execute('SELECT * FROM notifications ORDER BY id DESC LIMIT 60')]
    return {'assignments':[db.assignment(row) for row in rows], 'notifications':notifications,
            'last_sync':db.get('last_sync'),'next_sync':db.get('next_sync'),'sync_error':db.get('sync_error'),
            'worker_error':db.get('worker_error'),'busy':operation_lock.locked(),'demo':config.DEMO}

@app.get('/api/settings',dependencies=[Depends(authenticated)])
def settings():
    with db.connect() as c: courses=[dict(row) for row in c.execute('SELECT * FROM courses ORDER BY name')]
    return {**{key:db.get(key) for key in ('poll_minutes','retention_days','model','paused','initial_days')},
            'courses':courses,'google_configured':bool(config.GOOGLE_ID and config.GOOGLE_SECRET),
            'google_connected':bool(db.get('google_tokens')),'gemini_configured':bool(db.get('gemini_key') or config.GEMINI_KEY),
            'email_configured':bool(__import__('os').getenv('SMTP_HOST') and __import__('os').getenv('NOTIFY_EMAIL')),
            'email_error':db.get('email_error'),'callback_url':config.CALLBACK,'demo':config.DEMO}

class Settings(BaseModel):
    poll_minutes:int=Field(ge=15,le=1440)
    retention_days:int=Field(ge=7,le=365)
    initial_days:int=Field(ge=1,le=365)
    model:str=Field(pattern=r'^[a-zA-Z0-9._-]{1,80}$')
    paused:bool
    selected_courses:list[str]=Field(max_length=100)
    gemini_key:str|None=Field(default=None,max_length=300)

@app.put('/api/settings',dependencies=[Depends(authenticated)])
def save_settings(body:Settings):
    if config.DEMO: raise HTTPException(400,'Demo mode does not save settings.')
    with idle_required():
        for key in ('poll_minutes','retention_days','initial_days','model','paused'): db.set_value(key,getattr(body,key))
        if body.gemini_key and body.gemini_key.strip(): db.save_secret('gemini_key',body.gemini_key.strip())
        with db.connect() as c:
            c.execute('UPDATE courses SET selected=0')
            c.executemany('UPDATE courses SET selected=1 WHERE id=?',[(x,) for x in body.selected_courses])
        db.set_value('check_requested',True)
    return {'ok':True}

@app.post('/api/check',dependencies=[Depends(authenticated)])
def check():
    if config.DEMO: return {'ok':True}
    if not db.get('google_tokens'): raise HTTPException(400,'Connect your Google account in Settings first.')
    if db.get('paused'): raise HTTPException(400,'Resume automatic processing in Settings first.')
    db.set_value('check_requested',True); return {'ok':True}

@app.post('/api/manual-assignments',dependencies=[Depends(authenticated)])
async def create_manual_assignment(title:str=Form(max_length=200),course_id:str=Form(max_length=200),description:str=Form(default='',max_length=20000),due:str|None=Form(default=None,max_length=80),files:list[UploadFile]=File(default=[])):
    if config.DEMO: raise HTTPException(400,'Manual assignments are disabled in demo mode.')
    title=title.strip(); description=description.strip()
    if not title: raise HTTPException(400,'Enter an assignment title.')
    if not description and not files: raise HTTPException(400,'Add instructions or attach at least one source file.')
    if len(files)>20: raise HTTPException(400,'Attach up to 20 files per assignment.')
    due_value=None
    if due:
        try:
            parsed=datetime.fromisoformat(due.replace('Z','+00:00'))
            due_value=(parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)).isoformat()
        except ValueError: raise HTTPException(400,'Enter a valid due date and time.')
    allowed={'.pdf','.docx','.pptx','.xlsx','.txt','.csv','.png','.jpg','.jpeg','.webp','.gif'}
    fixed_mimes={'.pdf':'application/pdf','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation','.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','.txt':'text/plain','.csv':'text/csv','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.gif':'image/gif'}
    assignment_id='manual:'+uuid.uuid4().hex; folder=uuid.uuid4().hex; target=config.DATA/'files'/'manual_sources'/folder
    materials=[]; total=0
    try:
        target.mkdir(parents=True,exist_ok=False,mode=0o700)
        for index,upload in enumerate(files):
            raw_name=(upload.filename or '').replace('\\','/')
            name=Path(raw_name).name.strip()
            suffix=Path(name).suffix.lower()
            if not name or len(name)>200 or suffix not in allowed: raise HTTPException(400,'Supported uploads: PDF, DOCX, PPTX, XLSX, TXT, CSV, PNG, JPEG, WebP, or GIF.')
            content=await upload.read(config.MAX_FILE_BYTES+1)
            if len(content)>config.MAX_FILE_BYTES: raise HTTPException(413,f'{name} exceeds the 20 MB per-file limit.')
            total+=len(content)
            if total>config.MAX_TOTAL_BYTES: raise HTTPException(413,'Combined uploads exceed the 60 MB limit.')
            stored=f'{index:02d}-{uuid.uuid4().hex}{suffix}'
            path=target/stored
            with path.open('xb') as output:
                output.write(content)
            path.chmod(0o600)
            materials.append({'localFile':{'name':name,'mimeType':fixed_mimes[suffix],'path':str(path.relative_to(config.DATA/'files'))}})
        with idle_required():
            with db.connect() as c:
                course=c.execute('SELECT id,name FROM courses WHERE id=?',(course_id,)).fetchone()
                if not course: raise HTTPException(404,'Choose a class from your connected Classroom list.')
                now=time.time(); revision=hashlib.sha256(json.dumps({'title':title,'description':description,'due':due_value,'materials':materials},sort_keys=True).encode()).hexdigest()
                c.execute('''INSERT INTO assignments(id,course_id,source,title,description,due,materials,revision,status,stage,created,updated,submission_state)
                             VALUES(?,?, 'manual',?,?,?,?,?,'queued','Waiting to draft',?,?, '')''',
                          (assignment_id,course_id,title,description,due_value,json.dumps(materials),revision,now,now))
        db.notify('new','Manual assignment added: '+title,assignment_id)
        return {'id':assignment_id}
    except Exception:
        shutil.rmtree(target,ignore_errors=True)
        raise

@app.post('/api/assignments/{id}/retry',dependencies=[Depends(authenticated)])
def retry(id:str):
    if config.DEMO: raise HTTPException(400,'Retries are disabled in demo mode.')
    with idle_required():
        with db.connect() as c:
            row=c.execute('SELECT a.*,c.selected FROM assignments a JOIN courses c ON c.id=a.course_id WHERE a.id=?',(id,)).fetchone()
        if not row: raise HTTPException(404,'Assignment not found.')
        if not row['selected'] and row['source']!='manual': raise HTTPException(400,'Select this class in Settings before retrying.')
        if row['source']=='manual' and row['status']=='expired': raise HTTPException(400,'This assignment’s uploaded source files expired. Add it again to create a new draft.')
        if row['submission_state'] in ('TURNED_IN','RETURNED'): raise HTTPException(400,'This assignment is already submitted or returned.')
        if row['status']=='processing': raise HTTPException(409,'This assignment is already processing.')
        db.update_assignment(id,status='queued',stage='Waiting to draft',attempts=0,available_at=0,error=None)
    return {'ok':True}

@app.post('/api/assignments/{id}/complete',dependencies=[Depends(authenticated)])
def complete_assignment(id:str):
    if config.DEMO: raise HTTPException(400,'Assignment review changes are disabled in demo mode.')
    with idle_required():
        with db.connect() as c:
            row=c.execute('SELECT status FROM assignments WHERE id=?',(id,)).fetchone()
        if not row: raise HTTPException(404,'Assignment not found.')
        if row['status'] not in ('ready','completed'): raise HTTPException(400,'Only ready drafts can be marked completed or moved back to review.')
        if row['status']=='ready': db.update_assignment(id,status='completed',stage='Marked complete by you',error=None)
        else: db.update_assignment(id,status='ready',stage='Draft ready for your review',error=None)
    return {'ok':True}

@app.post('/api/notifications/read',dependencies=[Depends(authenticated)])
def notifications_read():
    with db.connect() as c: c.execute('UPDATE notifications SET seen=1')
    return {'ok':True}

@app.get('/api/assignments/{id}/files/{name}',dependencies=[Depends(authenticated)])
def download(id:str,name:str):
    with db.connect() as c: row=c.execute('SELECT files FROM assignments WHERE id=?',(id,)).fetchone()
    if not row: raise HTTPException(404,'Assignment not found.')
    file=next((f for f in json.loads(row['files']) if f['name']==name),None)
    if not file: raise HTTPException(404,'File not found.')
    root=(config.DATA/'files').resolve(); path=(root/file['path']).resolve()
    if not path.is_relative_to(root) or not path.is_file(): raise HTTPException(404,'File no longer available.')
    return FileResponse(path,filename=name,media_type='application/octet-stream')

@app.get('/api/google/connect',dependencies=[Depends(authenticated)])
async def google_connect(request:Request):
    if config.DEMO or not (config.GOOGLE_ID and config.GOOGLE_SECRET): raise HTTPException(400,'Configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in the server environment first.')
    state=secrets.token_urlsafe(32); request.session['oauth_state']=state; request.session['oauth_started']=time.time()
    params={'client_id':config.GOOGLE_ID,'redirect_uri':config.CALLBACK,'response_type':'code','scope':' '.join(config.SCOPES),'access_type':'offline','prompt':'consent','state':state}
    return RedirectResponse('https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(params))

@app.get('/api/google/callback',dependencies=[Depends(authenticated)])
async def google_callback(request:Request):
    state=request.session.pop('oauth_state',None); started=request.session.pop('oauth_started',0)
    if not state or not hmac.compare_digest(state,request.query_params.get('state','')) or time.time()-started>600:
        raise HTTPException(400,'Authorization expired. Start Google connection again from Settings.')
    if request.query_params.get('error'): return RedirectResponse('/?connection=denied')
    code=request.query_params.get('code')
    if not code: raise HTTPException(400,'Missing authorization code.')
    async with httpx.AsyncClient(timeout=30) as client:
        response=await client.post('https://oauth2.googleapis.com/token',data={'code':code,'client_id':config.GOOGLE_ID,'client_secret':config.GOOGLE_SECRET,'redirect_uri':config.CALLBACK,'grant_type':'authorization_code'})
    if response.status_code!=200: raise HTTPException(400,'Google connection failed. Check the exact redirect URL in Google Cloud.')
    tokens=response.json()
    if not tokens.get('refresh_token'): raise HTTPException(400,'Google did not return offline access. Revoke the existing app grant and connect again.')
    # Google may return normalized scope names that differ from the requested
    # strings even when the equivalent permissions were granted. Let the API
    # calls validate effective access; their 403 responses are surfaced as a
    # reconnect/permissions error by the worker.
    with idle_required():
        tokens['expires_at']=time.time()+tokens.get('expires_in',3600)
        db.save_secret('google_tokens',tokens); db.set_value('check_requested',True)
    return RedirectResponse('/?connection=success')

@app.post('/api/google/disconnect',dependencies=[Depends(authenticated)])
def disconnect():
    with idle_required():
        tokens=db.secret('google_tokens')
        if tokens:
            try:
                with httpx.Client(timeout=15) as client:
                    response=client.post('https://oauth2.googleapis.com/revoke',data={'token':tokens.get('refresh_token',tokens.get('access_token'))})
                    if response.status_code not in (200,400): raise HTTPException(502,'Google token revocation failed. Try again or revoke access in your Google Account.')
            except httpx.HTTPError: raise HTTPException(502,'Could not reach Google to revoke access. Please try again.')
        db.save_secret('google_tokens',None)
    return {'ok':True}

class DeleteData(BaseModel): confirmation:str
@app.post('/api/data/delete',dependencies=[Depends(authenticated)])
def delete_data(body:DeleteData):
    if body.confirmation!='DELETE': raise HTTPException(400,'Type DELETE to confirm.')
    if config.DEMO: raise HTTPException(400,'Data deletion is disabled in demo mode.')
    with idle_required():
        if db.get('google_tokens'): raise HTTPException(400,'Disconnect Google first so its access token can be revoked.')
        with db.connect() as c:
            for table in ('assignments','notifications','courses','settings'): c.execute('DELETE FROM '+table)
        shutil.rmtree(config.DATA/'files',ignore_errors=True)
        db.init()
    return {'ok':True}

@app.get('/health')
def health(): return {'status':'ok'}

static=config.ROOT/'frontend'/'dist'
if static.exists():
    app.mount('/',StaticFiles(directory=static,html=True),name='frontend')
