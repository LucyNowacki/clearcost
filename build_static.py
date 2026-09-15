"""Build a self-contained Pages demo; never export local review history or call a model."""
import argparse
import hashlib
import html
import json
import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import dashboard
from analytics import analyse
from geography import coverage
from reconcile import run

ROOT = Path(__file__).resolve().parent


def build(destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as temp:
        db, report = Path(temp)/'demo.sqlite3', Path(temp)/'report.json'
        run(ROOT/'Data/Contracts', db, report)
        store = dashboard.ReviewStore(db, report)
        data = {'report': store.report(), 'analysis': analyse(store),
                'geography': coverage(store), 'links': dashboard.extraction_links(store.report())}
    # ReviewStore creates evidence IDs from the original evidence; remove machine paths only afterwards.
    for c in data['report']['contracts']:
        for line in c['lines']:
            line['evidence']['contract_file'] = f"documents/{c['contract_id']}/contract.pdf"
        docdir = destination/'documents'/c['contract_id']
        docdir.mkdir(parents=True, exist_ok=True)
        for name in ('contract.pdf', 'invoice.pdf'):
            shutil.copyfile(ROOT/'Data/Contracts'/c['scenario_folder']/name, docdir/name)
    for link in data['links'].values():
        link['url'] = link['url'].replace('/extractions?', 'extractions.html?')
    # Stable storage scope across rebuilds when the source evidence is unchanged.
    data['dataset_id'] = hashlib.sha256(json.dumps([
        (c['contract_id'], c['sources']) for c in data['report']['contracts']], sort_keys=True).encode()).hexdigest()[:20]
    (destination/'data.json').write_text(json.dumps(data, ensure_ascii=False))
    shutil.copyfile(ROOT/'web/uk-outline.json', destination/'uk-outline.json')
    shutil.copyfile(ROOT/'web/static-demo.js', destination/'static-demo.js')
    shutil.copyfile(ROOT/'web/MAP_SOURCE.md', destination/'MAP_SOURCE.md')
    (destination/'.nojekyll').touch()
    for page in ('index', 'analysis', 'geography', 'guidance', 'readme'):
        text = (ROOT/'web'/f'{page}.html').read_text()
        # Only the exported copy changes; the local Python application remains intact.
        text = text.replace('fetch(', 'demoFetch(')
        text = text.replace('/api/document?', 'document.html?')
        text = re.sub(r'href="/(analysis|geography|extractions|guidance|readme)(?=[?"#])', r'href="\1.html', text)
        text = text.replace('href="/?', 'href="index.html?').replace('href="/"', 'href="index.html"')
        text = text.replace('Local workspace', 'Browser workspace').replace('Synthetic data · Local demo', 'Synthetic data · Browser demo')
        text = text.replace('</head>', '<script src="static-demo.js"></script></head>')
        if page == 'index':
            text = text.replace("const $=", "window.addEventListener('clearcost-reset',()=>{dirty=false});\nconst $=", 1)
        if page in ('guidance', 'readme'):
            text = adapt_explanation(text)
        (destination/f'{page}.html').write_text(text)
    drafts, skipped = dashboard.read_drafts()
    pieces = []
    for file, draft in drafts:
        cid = next((cid for cid, link in data['links'].items() if file.stem in link['url']), None)
        if cid is None:
            continue
        company = next(c['contractor'] for c in data['report']['contracts'] if c['contract_id'] == cid)
        rows = ''.join('<tr>'+''.join('<td>'+html.escape(str(t.get(k) or '—'))+'</td>' for k in ('field','value','quote','page'))+'</tr>' for t in draft['extraction']['terms'])
        pieces.append(f'<section data-draft="{file.stem}" id="draft-{file.stem}"><h2>{html.escape(company)} · {cid}</h2><p>Saved model: {html.escape(draft["model"])} · {html.escape(data["links"][cid]["status"])} · requires human review</p><p>{html.escape("; ".join(draft["extraction"]["warnings"]))}</p><a href="documents/{cid}/contract.pdf">Open source contract</a><div style="overflow:auto"><table><tr><th>Term</th><th>Value</th><th>Quotation</th><th>Page</th></tr>{rows}</table></div></section>')
    (destination/'extractions.html').write_text(simple_page('Contract extraction drafts', '<p>Pre-generated model outputs. No live model calls; these terms support human review and do not drive calculations.</p>'+''.join(pieces)+f'<p>{skipped} unreadable draft files omitted during export.</p>'+'''<script>const chosen=new URLSearchParams(location.search).get('draft');if(chosen){let found=false;document.querySelectorAll('[data-draft]').forEach(s=>{s.hidden=s.dataset.draft!==chosen;if(!s.hidden)found=true});if(!found)document.querySelector('main').append('This draft is not available in the published examples.');}</script>'''))
    (destination/'document.html').write_text(simple_page('Source document', '''<p id="document-message">Opening the source PDF…</p><script>const q=new URLSearchParams(location.search);ClearcostDemo.ready.then(data=>{const cid=q.get('contract'),kind=q.get('kind');if(!data.report.contracts.some(c=>c.contract_id===cid)||!['contract','invoice'].includes(kind))throw Error('Document not found.');location.replace('documents/'+encodeURIComponent(cid)+'/'+kind+'.pdf'+location.hash)}).catch(e=>document.getElementById('document-message').textContent=e.message);</script>'''))
    return data


def adapt_explanation(text):
    # Existing diagrams describe the Python source architecture, not a browser-hosted server.
    banner = '<section class="panel" style="padding:22px;margin-bottom:22px"><h2>This browser edition</h2><p>Python generates the example findings before publication. Here, JavaScript reads those saved results and keeps your review decisions in this browser only. No Python server, shared review database or model runs online. Clear browser data or choose Reset demo to remove your reviews. Tabs in this browser share your progress; other browsers and devices do not.</p></section>'
    text = text.replace('</header>', '</header>'+banner, 1)
    text = text.replace('The application at a glance', 'Original Python workflow · results precomputed for this edition')
    text = text.replace('One workspace, connected views', 'Local Python edition · connected views')
    text = text.replace('From files to Python to the browser', 'Source implementation · Python runs before publication')
    text = text.replace('Local reviewers share one database. Typed names are not authenticated accounts.', 'The original local edition uses a shared database. This browser edition keeps reviews on your device; typed names are not authenticated accounts.')
    text = text.replace('reviewers share the running demo’s database; typed reviewer names are not authenticated accounts.', 'the original local Python edition shares a database. This browser edition stores reviews on your device; names are not authenticated accounts.')
    text = text.replace('Save → SQLite review history → refreshed progress and summaries.', 'Local Python: Save → SQLite history → refreshed summaries.')
    text = text.replace('What is saved, and what remains outside the demo', 'What is saved in this browser edition')
    text = text.replace('Python performs the checks and serves the application; browser JavaScript displays the findings, charts and map. Saved decisions and history are stored in a local SQLite database, so work can continue after restarting. Original source CSVs and PDFs stay unchanged.', 'Python prepares the checks before publication. Browser JavaScript displays the saved findings, charts and map, and stores your decisions and history in this browser’s local storage. They survive refreshing or reopening in the same browser, unless its site data is cleared. Other browsers and devices start independently. Original source CSVs and PDFs stay unchanged.')
    text = text.replace('Reviewers share the local database; typed reviewer names are not authenticated accounts.', 'This demo has no shared review database; typed reviewer names are not authenticated accounts.')
    text = text.replace('General uploads, approved model terms driving calculations, Google Sheets integration and public hosting are not yet implemented.', 'General uploads, approved model terms driving calculations and Google Sheets integration are not implemented.')
    return text


def simple_page(title, body):
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>body{font:16px/1.6 system-ui;color:#19352e;background:#f4f6ef;margin:30px auto;padding:20px;max-width:1100px}a{color:#245d49}nav{display:flex;gap:20px;flex-wrap:wrap}table{border-collapse:collapse;width:100%}td,th{border:1px solid #cbd6c8;padding:12px;text-align:left}section{background:white;padding:20px;margin:20px 0;border-radius:12px}p{overflow-wrap:anywhere}</style><script src="static-demo.js"></script></head><body><header><h1>Clearcost</h1><p>Energy Contractor Cost Reconciliation<br>A portfolio demo by Lucy Nowacki</p></header><nav><a href="index.html">Invoice review</a><a href="analysis.html">Data analysis</a><a href="geography.html">Geography</a><a href="guidance.html">Guidance</a><a href="readme.html">Introduction to the Application</a></nav><main><h1>'+title+'</h1>'+body+'</main></body></html>'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'dist/clearcost')
    args = parser.parse_args()
    build(args.output)
    print(f'Browser demo built in {args.output}')
