import json
import time
from datetime import datetime,timedelta,timezone
from . import config,db
from .documents import Draft,Section,Slide,Calculation,render

def seed():
    with db.connect() as c:
        if c.execute('SELECT count(*) FROM assignments').fetchone()[0]: return
        for id,name in [('financial','Financial Accounting'),('finance','Corporate Finance'),('business','Business Communication')]:
            c.execute('INSERT INTO courses(id,name,selected) VALUES(?,?,1)',(id,name))
    draft=Draft(title='Time Value of Money',summary='A short explanation of present value, future value and discounting.',formats=['docx','pptx'],sections=[Section(heading='Present value',paragraphs=['Present value converts a future cash flow into today’s equivalent value. For a single payment, PV = FV / (1 + r)^n, where r is the discount rate and n is the number of periods.'],table_headers=['Input','Value'],table_rows=[['Future cash flow','$10,000'],['Annual discount rate','8%'],['Number of years','3']]),Section(heading='Worked example',paragraphs=['For $10,000 received in three years at an 8% annual discount rate, the present value is approximately $7,938.32. The calculation assumes annual compounding and a constant discount rate.'])],slides=[Slide(title='What is present value?',bullets=['Money today can earn a return.','Discounting makes future payments comparable with cash today.'],notes='Discuss opportunity cost and the chosen discount rate.'),Slide(title='A worked example',bullets=['Future cash flow: $10,000','Discount rate: 8% per year','Time: 3 years','Present value: approximately $7,938.32'])],sources=['Illustrative demo content; no Classroom data used.'],assumptions=['Annual compounding and constant discount rate.'],review_notes=['Demo only. Confirm methods and rounding required by your course.'],calculations=[Calculation(label='Present value',expression='10000 / (1.08 ** 3)')])
    files=render(draft,config.DATA/'files'/'demo')
    for file in files: file['path']='demo/'+file['name']
    items=[('finance','Time Value of Money','Create a document and presentation explaining discounting, with a worked example.','ready','Draft ready for your review',2,draft.model_dump_json(),json.dumps(files)),('financial','Cash flow statement analysis','Prepare an analysis of operating, investing and financing cash flows.','queued','Demo preview — no live processing',4,None,'[]'),('business','Business report: quarterly performance','Write a concise report using the attached case study.','attention','Needs attention',6,None,'[]')]
    with db.connect() as c:
        for course,title,description,status,stage,days,content,file_json in items:
            id=course+':demo'
            c.execute('''INSERT INTO assignments(id,course_id,title,description,due,revision,status,stage,error,created,updated,draft,files)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(id,course,title,description,(datetime.now(timezone.utc)+timedelta(days=days)).isoformat(),'demo',status,stage,'A scanned PDF needs OCR before processing.' if status=='attention' else None,time.time(),time.time(),content,file_json))
    db.notify('ready','Draft ready: Time Value of Money','finance:demo')
    db.notify('new','New assignment: Cash flow statement analysis','financial:demo')
