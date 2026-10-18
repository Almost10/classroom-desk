import base64
import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from cryptography.fernet import Fernet
from . import config

cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(config.SECRET.encode()).digest()))

@contextmanager
def connect():
    conn = sqlite3.connect(config.DATA / 'desk.sqlite3', timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init():
    config.DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    (config.DATA / 'files').mkdir(exist_ok=True, mode=0o700)
    with connect() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS courses(id TEXT PRIMARY KEY,name TEXT NOT NULL,section TEXT NOT NULL DEFAULT '',selected INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS assignments(
          id TEXT PRIMARY KEY,course_id TEXT NOT NULL,source TEXT NOT NULL DEFAULT 'classroom',title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',
          due TEXT,link TEXT NOT NULL DEFAULT '',materials TEXT NOT NULL DEFAULT '[]',revision TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'new',stage TEXT NOT NULL DEFAULT '',error TEXT,attempts INTEGER NOT NULL DEFAULT 0,
          available_at REAL NOT NULL DEFAULT 0,created REAL NOT NULL,updated REAL NOT NULL,
          submission_state TEXT NOT NULL DEFAULT '',draft TEXT,files TEXT NOT NULL DEFAULT '[]',notified_ready INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,message TEXT NOT NULL,assignment_id TEXT,created REAL NOT NULL,seen INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS assignment_queue ON assignments(status,available_at);
        ''')
        columns={row['name'] for row in c.execute('PRAGMA table_info(assignments)')}
        if 'source' not in columns:
            c.execute("ALTER TABLE assignments ADD COLUMN source TEXT NOT NULL DEFAULT 'classroom'")
        defaults = {'poll_minutes':180,'retention_days':90,'model':'gemini-3.8-flash','paused':False,
                    'initial_days':30,'last_sync':None,'sync_error':None,'next_sync':0,'check_requested':False}
        for key,value in defaults.items():
            c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(key,json.dumps(value)))
        c.execute("UPDATE assignments SET status='queued',stage='Resuming after restart' WHERE status='processing'")
    (config.DATA / 'desk.sqlite3').chmod(0o600)

def get(key, default=None):
    with connect() as c:
        row=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        return json.loads(row['value']) if row else default

def set_value(key,value):
    with connect() as c:
        c.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value)))

def secret(key):
    value=get(key)
    return json.loads(cipher.decrypt(value.encode())) if value else None

def save_secret(key,value):
    set_value(key,cipher.encrypt(json.dumps(value).encode()).decode() if value is not None else None)

def notify(kind,message,assignment_id=None):
    with connect() as c:
        c.execute('INSERT INTO notifications(kind,message,assignment_id,created) VALUES(?,?,?,?)',(kind,message,assignment_id,time.time()))

def assignment(row):
    result=dict(row)
    for key in ('materials','files','draft'):
        result[key]=json.loads(result[key]) if result[key] else None
    return result

def update_assignment(id,**values):
    values['updated']=time.time()
    with connect() as c:
        c.execute('UPDATE assignments SET '+','.join(k+'=?' for k in values)+' WHERE id=?',(*values.values(),id))
