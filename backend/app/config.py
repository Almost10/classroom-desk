import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
DATA = Path(os.getenv('DATA_DIR', str(ROOT / 'data'))).resolve()
BASE_URL = os.getenv('BASE_URL', 'http://localhost:8000').rstrip('/')
SECRET = os.getenv('APP_SECRET', '')
PASSWORD = os.getenv('APP_PASSWORD', '')
DEMO = os.getenv('DEMO_MODE', 'false').lower() == 'true'
if len(SECRET) < 32 or len(PASSWORD) < 12:
    raise RuntimeError('Run python3 scripts/setup.py first; APP_SECRET and a 12+ character APP_PASSWORD are required.')
GOOGLE_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GEMINI_KEY = os.getenv('GEMINI_API_KEY', '')
CALLBACK = BASE_URL + '/api/google/callback'
SCOPES = ['https://www.googleapis.com/auth/classroom.courses.readonly',
          'https://www.googleapis.com/auth/classroom.coursework.me.readonly',
          'https://www.googleapis.com/auth/drive.readonly']
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 60 * 1024 * 1024
MAX_SOURCE_CHARS = 220000
