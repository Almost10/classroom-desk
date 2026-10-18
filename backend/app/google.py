import time
import httpx
from . import config,db

class IntegrationError(Exception):
    def __init__(self,message,retry=False,quota=False):
        super().__init__(message)
        self.retry=retry
        self.quota=quota

class Google:
    def __init__(self):
        self.tokens=db.secret('google_tokens')
        if not self.tokens:
            raise IntegrationError('Connect Google in Settings to check Classroom.')
        self.client=httpx.Client(timeout=60,follow_redirects=False)

    def __enter__(self): return self
    def __exit__(self,*args): self.client.close()

    def token(self):
        if self.tokens.get('expires_at',0)<time.time()+90:
            response=self.client.post('https://oauth2.googleapis.com/token',data={
                'client_id':config.GOOGLE_ID,'client_secret':config.GOOGLE_SECRET,
                'refresh_token':self.tokens.get('refresh_token',''),'grant_type':'refresh_token'})
            if response.status_code != 200:
                raise IntegrationError('Google authorization expired or was revoked. Reconnect Google in Settings.',retry=response.status_code>=500)
            self.tokens.update(response.json())
            self.tokens['expires_at']=time.time()+self.tokens.get('expires_in',3600)
            db.save_secret('google_tokens',self.tokens)
        return self.tokens['access_token']

    def request(self,url,params=None):
        response=self.client.get(url,params=params,headers={'Authorization':'Bearer '+self.token()})
        if response.status_code!=200:
            if response.status_code in (401,403):
                raise IntegrationError('Google denied access. Check Classroom/Drive APIs and consent permissions, then reconnect.')
            if response.status_code==404: raise IntegrationError('An attached file or Classroom item is no longer available.')
            raise IntegrationError('Google is temporarily unavailable or rate limited.',retry=response.status_code==429 or response.status_code>=500)
        return response

    def pages(self,url,key,params=None):
        params=dict(params or {})
        while True:
            data=self.request(url,params).json()
            yield from data.get(key,[])
            if not data.get('nextPageToken'): break
            params['pageToken']=data['nextPageToken']

    def courses(self):
        return list(self.pages('https://classroom.googleapis.com/v1/courses','courses',{'courseStates':'ACTIVE','pageSize':100}))

    def coursework(self,id):
        return list(self.pages(f'https://classroom.googleapis.com/v1/courses/{id}/courseWork','courseWork',{'courseWorkStates':'PUBLISHED','pageSize':100}))

    def submissions(self,id):
        rows=self.pages(f'https://classroom.googleapis.com/v1/courses/{id}/courseWork/-/studentSubmissions','studentSubmissions',{'userId':'me','pageSize':100})
        return {row['courseWorkId']:row.get('state','') for row in rows}

    def attachment(self,id):
        url='https://www.googleapis.com/drive/v3/files/'+id
        meta=self.request(url,{'fields':'id,name,mimeType,size'}).json()
        if int(meta.get('size',0))>config.MAX_FILE_BYTES:
            raise IntegrationError(f'Attachment exceeds the 20 MB limit: {meta["name"]}')
        exports={'application/vnd.google-apps.document':'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                 'application/vnd.google-apps.presentation':'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                 'application/vnd.google-apps.spreadsheet':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
        mime=meta['mimeType']
        if mime.startswith('application/vnd.google-apps.') and mime not in exports:
            raise IntegrationError(f'Unsupported Google file type: {meta["name"]}. Export it to PDF or DOCX first.')
        params={'mimeType':exports[mime]} if mime in exports else {'alt':'media'}
        endpoint=url+'/export' if mime in exports else url
        # Stream to enforce the cap even if Google does not report file size.
        with self.client.stream('GET',endpoint,params=params,headers={'Authorization':'Bearer '+self.token()}) as response:
            if response.status_code!=200:
                raise IntegrationError(f'Cannot read attachment: {meta["name"]}',retry=response.status_code==429 or response.status_code>=500)
            data=bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data)>config.MAX_FILE_BYTES: raise IntegrationError('Attachment exceeds the 20 MB download limit.')
        return meta['name'],exports.get(mime,mime),bytes(data)
