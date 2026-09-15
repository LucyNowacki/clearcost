"""Local review dashboard. Run: python dashboard.py (then open localhost:8765)."""
from contextlib import closing
import argparse
import hashlib
import html
from finding_evidence import evidence_for
from analytics import analyse
from geography import coverage
import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT=Path(__file__).resolve().parent
STATUSES={'needs_review','awaiting_evidence','confirmed_error','valid_charge'}


class ReviewStore:
    def __init__(self, db_path, report_path):
        self.db_path=Path(db_path);self.report_path=Path(report_path)
        with closing(sqlite3.connect(self.db_path)) as c, c:
            c.execute('''CREATE TABLE IF NOT EXISTS review_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, evidence_key TEXT NOT NULL,
                contract_id TEXT NOT NULL, line_id TEXT NOT NULL, status TEXT NOT NULL,
                reviewer TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL)''')

    def report(self):
        r=json.loads(self.report_path.read_text())
        for contract in r['contracts']:
            for line in contract['lines']:
                payload={'sources':contract['sources'],'contract_id':contract['contract_id'],'line':line}
                line['evidence_key']=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        return r

    def events(self):
        with closing(sqlite3.connect(self.db_path)) as c, c:
            c.row_factory=sqlite3.Row
            return [dict(r) for r in c.execute('SELECT * FROM review_events ORDER BY id DESC')]

    def save(self, data):
        if data.get('status') not in STATUSES:raise ValueError('Choose a valid review decision.')
        reviewer=data.get('reviewer');note=data.get('note')
        if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>100:
            raise ValueError('Enter a reviewer name (up to 100 characters).')
        if not isinstance(note,str) or len(note)>4000:raise ValueError('Notes must be at most 4,000 characters.')
        if data['status'] in {'confirmed_error','valid_charge'} and not note.strip():
            raise ValueError('Add a reason for your decision.')
        found=None
        for contract in self.report()['contracts']:
            for line in contract['lines']:
                if line['evidence_key']==data.get('evidence_key'):found=(contract,line)
        if found is None:raise ValueError('Evidence changed or finding no longer exists. Refresh before saving.')
        contract,line=found
        with closing(sqlite3.connect(self.db_path,timeout=10)) as c, c:
            c.execute('BEGIN IMMEDIATE')
            previous=c.execute('SELECT id,status,reviewer,note FROM review_events WHERE evidence_key=? ORDER BY id DESC LIMIT 1',(line['evidence_key'],)).fetchone()
            if previous and previous[1:]==(data['status'],reviewer.strip(),note.strip()):
                return {'saved':False,'unchanged':True}
            current=previous[0] if previous else 0
            if data.get('expected_version')!=current:raise ValueError('Another review was saved. Refresh before saving your changes.')
            c.execute('INSERT INTO review_events(evidence_key,contract_id,line_id,status,reviewer,note,created_at) VALUES(?,?,?,?,?,?,?)',
                      (line['evidence_key'],contract['contract_id'],line['line_id'],data['status'],reviewer.strip(),note.strip(),datetime.now(timezone.utc).isoformat()))
        return {'saved':True}


def read_drafts():
    drafts=[];skipped=0;seen=set()
    files=[*(ROOT/'output'/'llm').glob('*.json'),*(ROOT/'Data'/'extraction_examples').glob('*.json')]
    for file in files:
        if file.stem in seen:continue
        try:
            draft=json.loads(file.read_text())
            if not isinstance(draft,dict):raise ValueError('Invalid draft object')
            if draft.get('status')!='draft_needs_human_review':continue
            for key in ('source','source_sha256','model','created_at'):
                if not isinstance(draft.get(key),str):raise ValueError('Invalid draft metadata')
            extraction=draft.get('extraction')
            if not isinstance(extraction,dict) or not isinstance(extraction.get('terms'),list) or not isinstance(extraction.get('warnings'),list):raise ValueError('Invalid extraction')
            if not all(isinstance(w,str) for w in extraction['warnings']):raise ValueError('Invalid warnings')
            for term in extraction['terms']:
                if not isinstance(term,dict) or not isinstance(term.get('field'),str):raise ValueError('Invalid term')
                if not all(key in term and (term[key] is None or isinstance(term[key],str)) for key in ('value','quote','uncertainty')):raise ValueError('Invalid term text')
                if 'page' not in term or (term['page'] is not None and (type(term['page']) is not int or term['page']<1)):raise ValueError('Invalid page')
            source=Path(draft['source'])
            if not source.is_absolute():draft['source']=str((ROOT/source).resolve())
            drafts.append((file,draft));seen.add(file.stem)
        except (OSError,ValueError,TypeError):skipped+=1
    return drafts,skipped


def extraction_links(report):
    links={}
    drafts,_=read_drafts()
    for contract in report['contracts']:
        source=(ROOT/'Data'/'Contracts'/contract['scenario_folder']/'contract.pdf').resolve()
        matching=[(f,d) for f,d in drafts if Path(d.get('source','')).resolve()==source]
        if not matching:continue
        current=hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else None
        matching.sort(key=lambda pair:(pair[1].get('source_sha256')==current,pair[1].get('created_at','')),reverse=True)
        file,draft=matching[0]
        links[contract['contract_id']]={'status':'available' if draft.get('source_sha256')==current else 'stale',
            'url':'/extractions?draft='+file.stem+'#draft-'+file.stem,
            'model':draft.get('model','Unknown'),
            'findings':{line['line_id']:evidence_for(line,draft['extraction']) for line in contract['lines']} if draft.get('source_sha256')==current else {}}
    return links


def handler(store):
    class Handler(BaseHTTPRequestHandler):
        def send(self, code, body, kind='application/json'):
            if kind=='application/json':body=json.dumps(body).encode()
            self.send_response(code);self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)

        def allowed(self):
            host=self.headers.get('Host','')
            return host in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.allowed():return self.send(403,{'error':'Local requests only.'})
            url=urlparse(self.path)
            try:
                if url.path=='/':return self.send(200,(ROOT/'web'/'index.html').read_bytes(),'text/html; charset=utf-8')
                if url.path=='/api/extraction-links':return self.send(200,extraction_links(store.report()))
                if url.path=='/extractions':
                    selected_draft=parse_qs(url.query).get('draft',[''])[0]
                    entries=[]
                    drafts,skipped=read_drafts()
                    for file,draft in sorted(drafts):
                        if selected_draft and file.stem!=selected_draft:continue
                        source=Path(draft['source'])
                        stale=not source.exists() or hashlib.sha256(source.read_bytes()).hexdigest()!=draft['source_sha256']
                        terms=''.join('<tr><td>'+html.escape(t['field'])+'</td><td>'+html.escape(t['value'] or 'Unknown')+'</td><td>'+html.escape(t['quote'] or t['uncertainty'] or '')+'</td><td>'+html.escape(str(t['page'] or '—'))+'</td></tr>' for t in draft['extraction']['terms'])
                        warnings='; '.join(draft['extraction']['warnings'])
                        entries.append('<h2 id="draft-'+html.escape(file.stem)+'">'+html.escape(source.parent.name.split('_',1)[-1].replace('_',' ').title())+'</h2><p>Model: '+html.escape(draft.get('model','Unknown'))+'</p><p>'+('STALE SOURCE — re-extract before review.' if stale else 'Draft — meaning requires human review.')+'</p><p>'+html.escape(warnings)+'</p><table><tr><th>Term</th><th>Extracted value</th><th>Source passage / uncertainty</th><th>Page</th></tr>'+terms+'</table>')
                    page='<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Contract extraction drafts</title><style>body{font:16px/1.5 system-ui;background:#f4f6ef;color:#19352e;max-width:1100px;margin:40px auto;padding:20px}table{width:100%;border-collapse:collapse;background:white}td,th{padding:12px;text-align:left;border:1px solid #dbe3db;overflow-wrap:anywhere}a{color:#245d49}.portfolio-header{padding:0 0 20px;margin-bottom:24px;border-bottom:1px solid #dbe3db;color:#19352e}.portfolio-header strong{display:block;font-size:29px;letter-spacing:-.6px}.portfolio-header div{font-size:24px;margin-top:3px}.portfolio-header p{font-size:24px;margin:5px 0 0;color:#62736c}</style><header class="portfolio-header" aria-label="Application and author"><strong>Clearcost</strong><div>Energy Contractor Cost Reconciliation</div><p>A portfolio demo by Lucy Nowacki</p></header><a href="/">← Invoice review</a> <a href="/guidance" style="display:inline-block;padding:10px 16px;margin-left:16px;border-radius:9px;background:#ead7aa;color:#273c31;font-weight:700">Guidance ↗</a> <a href="/readme" style="display:inline-block;padding:10px 16px;margin-left:16px;border-radius:9px;background:#ead7aa;color:#273c31;font-weight:700">Introduction to the Application ↗</a><h1>Contract extraction drafts</h1><p>The selected language model extracts terms; a person must verify their meaning. These drafts do not change reconciliation calculations. Opening this page makes no model calls.</p>'+(f'<p>{skipped} unreadable draft file(s) skipped. Restore or regenerate them before review.</p>' if skipped else '')+(''.join(entries) or '<p>No live extraction drafts yet. Offline requests are prepared separately.</p>')+'</html>'
                    return self.send(200,page.encode(),'text/html; charset=utf-8')
                if url.path=='/readme':return self.send(200,(ROOT/'web'/'readme.html').read_bytes(),'text/html; charset=utf-8')
                if url.path=='/guidance':return self.send(200,(ROOT/'web'/'guidance.html').read_bytes(),'text/html; charset=utf-8')
                if url.path=='/analysis':return self.send(200,(ROOT/'web'/'analysis.html').read_bytes(),'text/html; charset=utf-8')
                if url.path=='/geography':return self.send(200,(ROOT/'web'/'geography.html').read_bytes(),'text/html; charset=utf-8')
                if url.path=='/api/geography':return self.send(200,coverage(store,ROOT/'Data'/'geography.json'))
                if url.path=='/api/map-outline':return self.send(200,json.loads((ROOT/'web'/'uk-outline.json').read_text()))
                if url.path=='/api/analysis':return self.send(200,analyse(store))
                if url.path=='/api/report':return self.send(200,store.report())
                if url.path=='/api/reviews':return self.send(200,store.events())
                if url.path=='/api/document':
                    q=parse_qs(url.query);cid=q.get('contract',[''])[0];kind=q.get('kind',[''])[0]
                    if kind not in {'contract','invoice'}:return self.send(404,{'error':'Document not found.'})
                    contract=next((c for c in store.report()['contracts'] if c['contract_id']==cid),None)
                    if contract:
                        base=(ROOT/'Data'/'Contracts').resolve()
                        p=(base/contract['scenario_folder']/(kind+'.pdf')).resolve()
                        if p.is_relative_to(base):return self.send(200,p.read_bytes(),'application/pdf')
                return self.send(404,{'error':'Not found.'})
            except sqlite3.Error:return self.send(503,{'error':'Stored data unavailable. Check the database and retry.'})
            except (OSError,ValueError,KeyError,TypeError,AttributeError):return self.send(500,{'error':'Data unavailable or malformed. Restore the source data and refresh.'})

        def do_POST(self):
            origin=self.headers.get('Origin')
            if not self.allowed() or origin not in {None,f'http://{self.headers.get("Host")}'}:
                return self.send(403,{'error':'Local same-origin requests only.'})
            if self.path!='/api/reviews':return self.send(404,{'error':'Not found.'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=12000:raise ValueError('Request size is invalid.')
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON required.')
                data=json.loads(self.rfile.read(size))
                if not isinstance(data,dict):raise ValueError('JSON object required.')
                return self.send(200,store.save(data))
            except (ValueError,TypeError) as exc:return self.send(400,{'error':str(exc)})
            except sqlite3.Error:return self.send(503,{'error':'Unable to save review. Please retry.'})
            except (OSError,KeyError,AttributeError):return self.send(500,{'error':'Review evidence unavailable. Restore the report and refresh before saving.'})

        def log_message(self, fmt,*args):pass
    return Handler


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8765)
    args=p.parse_args();db=ROOT/'output'/'reconciliation.sqlite3';report=ROOT/'output'/'reconciliation.json'
    if not db.exists() or not report.exists():p.error('Run python reconcile.py first.')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(ReviewStore(db,report)))
    print(f'Review dashboard: http://localhost:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
