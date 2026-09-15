"""Local, evidence-linked reconciliation for the five controlled demo contracts."""
from __future__ import annotations
from contextlib import closing

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent


def one(pattern: str, text: str) -> str:
    matches = re.findall(pattern, text)
    if len(matches) != 1:
        raise ValueError(f"Contract template is unsupported or ambiguous: {pattern}")
    return matches[0]


def pence(text: str) -> int:
    return int(Decimal(text) * 100)


def extract_terms(path: Path) -> dict:
    """Strict adapter for our authored template, not a general contract interpreter."""
    text = ' '.join(' '.join(page.extract_text() or '' for page in PdfReader(path).pages).split())
    for required in (
        'Synthetic demonstration data', 'Meter-services agreement',
        'Effective: 1-31 August 2026, inclusive.',
        'Incomplete visits have no charge.',
        'There are no other cancellation conditions or minimum charges',
        'Completed visits require a completion reference.',
        'Each job may appear once only.',
        'retain the earliest invoice line number',
        'No previous invoices exist for this scenario.',
        'All quantities are one.', 'All amounts are GBP before VAT.',
    ):
        if required not in text:
            raise ValueError(f"Unsupported contract wording: missing {required!r}")
    rate = pence(one(r'Each completed visit costs GBP (\d+\.\d{2}) before VAT', text))
    cancel = pence(one(r'A cancelled visit has a fixed charge of GBP (\d+\.\d{2})\.', text))
    approvals = {}
    pattern = r'Approval (APP-[\w-]+) authorises a supplement of GBP (\d+\.\d{2}) for completed job ([\w-]+) only, giving an agreed total of GBP (\d+\.\d{2})\.'
    found = re.findall(pattern, text)
    if found:
        if len(found) != 1 or 'There are no approved supplements' in text:
            raise ValueError('Ambiguous approval clauses')
        ref, supplement, job, total = found[0]
        if pence(total) != rate + pence(supplement):
            raise ValueError('Approval total does not equal rate plus supplement')
        approvals[job] = {'approval_id': ref, 'total_pence': pence(total)}
    elif 'There are no approved supplements or price amendments.' not in text:
        raise ValueError('Unrecognised approval clause')
    return dict(contract_id=one(r'Contract: (CTR-\d+)', text),
                version=one(r'Version: ([\d.]+)', text),
                service_type=one(r'The agreed service is ([^.]+)\.', text).replace(' ', '_'),
                period_start='2026-08-01', period_end='2026-08-31',
                standard_rate_pence=rate, cancelled_rate_pence=cancel,
                approvals=approvals, source_file=str(path),
                source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                source_text=text, extraction_method='controlled_template_v1')


def read_csv(path: Path, required: set[str]) -> list[dict]:
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if len(set(fields)) != len(fields) or not required.issubset(fields):
            raise ValueError(f'{path.name}: duplicate or missing column names')
        rows = list(reader)
    if not rows:
        raise ValueError(f'{path.name}: empty input')
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError(f'{path.name}: malformed row width')
    return rows


def unique(rows: list[dict], key: str) -> None:
    values = [r[key] for r in rows]
    if any(not v for v in values) or len(values) != len(set(values)):
        raise ValueError(f'Missing or duplicate {key}')


def iso(value: str) -> str:
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError(f'Expected ISO date: {value}')
    return value


def load_scenario(folder: Path) -> tuple[dict, list[dict], list[dict], list[dict]]:
    terms = extract_terms(folder / 'contract.pdf')
    visits = read_csv(folder / 'visits.csv', {'contract_id','job_id','service_date','service_type','status','completion_reference','approval_reference','contractor'})
    lines = read_csv(folder / 'invoice_lines.csv', {'contract_id','invoice_id','invoice_date','period_start','period_end','line_id','line_number','job_id','service_date','service_type','quantity','unit_rate_pence','line_amount_pence','currency','tax_basis','contractor'})
    unique(visits, 'job_id'); unique(lines, 'line_id')
    for rows in (visits, lines):
        for r in rows:
            if r['contract_id'] != terms['contract_id']:
                raise ValueError('CSV contract does not match PDF contract')
            iso(r['service_date'])
    names = {r['contractor'] for r in visits + lines}
    if len(names) != 1 or not next(iter(names)):
        raise ValueError('Contractor names are missing or inconsistent')
    terms['contractor'] = next(iter(names))
    if terms['contractor'] not in terms['source_text']:
        raise ValueError('CSV contractor name is absent from PDF')
    if len({r['invoice_id'] for r in lines}) != 1 or not lines[0]['invoice_id']:
        raise ValueError('One non-empty invoice identifier is required per scenario')
    headers = {(r['invoice_date'],r['period_start'],r['period_end']) for r in lines}
    if len(headers) != 1:
        raise ValueError('Inconsistent invoice dates or periods')
    for r in visits:
        if r['status'] not in {'completed','cancelled','incomplete'}:
            raise ValueError('Unknown visit status')
    for r in lines:
        for field in ('line_number','quantity','unit_rate_pence','line_amount_pence'):
            if not re.fullmatch(r'\d+', r[field]):
                raise ValueError(f'{field} must be a nonnegative integer')
            r[field] = int(r[field])
        if r['line_number'] < 1 or r['quantity'] != 1:
            raise ValueError('Template requires positive line numbers and quantity one')
        if r['currency'] != 'GBP' or r['tax_basis'] != 'exclusive_of_vat':
            raise ValueError('Only GBP amounts before VAT are supported')
        for field in ('invoice_date','period_start','period_end'): iso(r[field])
        if r['period_start'] > r['period_end']:
            raise ValueError('Invalid invoice period')
    unique(lines, 'line_number')
    sources = [dict(file=name,sha256=hashlib.sha256((folder/name).read_bytes()).hexdigest())
               for name in ('contract.pdf','visits.csv','invoice_lines.csv')]
    return terms, visits, lines, sources


def reconcile(terms: dict, visits: list[dict], lines: list[dict]) -> list[dict]:
    by_job = {r['job_id']: r for r in visits}
    seen = {}
    results = []
    for line in sorted(lines, key=lambda r:r['line_number']):
        job = line['job_id']; visit = by_job.get(job)
        previous = seen.setdefault(job, line['line_id'])
        issues = []; expected = None; clauses = []
        # Unverifiable records retain a null expected amount, never a false zero.
        if line['line_amount_pence'] != line['quantity'] * line['unit_rate_pence']:
            issues.append('line_arithmetic_mismatch')
        if not (terms['period_start'] <= line['service_date'] <= terms['period_end']
                and line['period_start'] <= line['service_date'] <= line['period_end']):
            issues.append('service_outside_period')
        if line['service_type'] != terms['service_type']:
            issues.append('unsupported_service')
        if visit is None:
            issues.append('missing_visit_record')
        else:
            if (visit['service_date'],visit['service_type']) != (line['service_date'],line['service_type']):
                issues.append('visit_details_mismatch')
            if visit['status']=='completed' and not visit['completion_reference']:
                issues.append('missing_completion_evidence')
            approval = terms['approvals'].get(job)
            if visit['approval_reference'] and (not approval or visit['approval_reference'] != approval['approval_id']):
                issues.append('unverified_approval')
            if approval and visit['approval_reference'] != approval['approval_id']:
                issues.append('missing_approval_reference')
        if previous != line['line_id']:
            issues.append('duplicate_job'); clauses.append('4')
        blocking = set(issues) - {'duplicate_job','line_arithmetic_mismatch'}
        if not blocking:
            if previous != line['line_id']:
                expected = 0
            elif visit['status']=='completed':
                expected = terms['approvals'].get(job,{}).get('total_pence',terms['standard_rate_pence'])
                clauses = ['1','3','5'] if job in terms['approvals'] else ['1','3']
                if line['unit_rate_pence'] != expected: issues.append('rate_mismatch')
            elif visit['status']=='cancelled':
                expected = terms['cancelled_rate_pence']; clauses=['2']
                if line['unit_rate_pence'] != expected: issues.append('cancelled_visit_rate_mismatch')
            else:
                expected=0;clauses=['2']
                if line['line_amount_pence']: issues.append('non_chargeable_incomplete')
        classification = 'unverified' if expected is None else issues[0] if issues else 'match'
        delta = None if expected is None else line['line_amount_pence']-expected
        explanation = ('Evidence is incomplete or inconsistent; expected cost is not yet determined.' if expected is None
                       else f"Billed GBP {line['line_amount_pence']/100:.2f}; contract-supported expected amount GBP {expected/100:.2f}; difference GBP {delta/100:.2f}.")
        results.append(dict(line_id=line['line_id'],job_id=job,classification=classification,issues=issues,
                            review_status='needs_review' if issues else 'matched',requires_review=bool(issues),
                            billed_pence=line['line_amount_pence'],expected_pence=expected,discrepancy_pence=delta,
                            explanation=explanation,contract_clauses=clauses,
                            evidence=dict(contract_file=terms['source_file'],contract_sha256=terms['source_sha256'],
                                          invoice_line_id=line['line_id'],visit_job_id=job if visit else None,
                                          previous_invoice_line_id=previous if previous!=line['line_id'] else None)))
    return results


def summarize(results: list[dict]) -> dict:
    unknown = [r for r in results if r['expected_pence'] is None]
    known_expected = sum(r['expected_pence'] for r in results if r['expected_pence'] is not None)
    known_delta = sum(r['discrepancy_pence'] for r in results if r['discrepancy_pence'] is not None)
    return dict(invoice_line_count=len(results),matched_line_count=sum(not r['requires_review'] for r in results),
                flagged_line_count=sum(r['requires_review'] for r in results),unverified_line_count=len(unknown),
                billed_total_pence=sum(r['billed_pence'] for r in results),
                known_expected_total_pence=known_expected,known_discrepancy_total_pence=known_delta,
                expected_total_pence=None if unknown else known_expected,
                discrepancy_total_pence=None if unknown else known_delta,
                unverified_billed_total_pence=sum(r['billed_pence'] for r in unknown),realised_savings_pence=0)


SCHEMA = '''
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS contracts(run_id TEXT, contract_id TEXT, terms_json TEXT NOT NULL,
 PRIMARY KEY(run_id,contract_id),FOREIGN KEY(run_id) REFERENCES runs(run_id));
CREATE TABLE IF NOT EXISTS sources(run_id TEXT, contract_id TEXT, file TEXT, sha256 TEXT,
 PRIMARY KEY(run_id,contract_id,file));
CREATE TABLE IF NOT EXISTS visits(run_id TEXT, contract_id TEXT, job_id TEXT, status TEXT, record_json TEXT,
 PRIMARY KEY(run_id,contract_id,job_id));
CREATE TABLE IF NOT EXISTS invoice_lines(run_id TEXT, contract_id TEXT, invoice_id TEXT, line_id TEXT,
 job_id TEXT, billed_pence INTEGER, record_json TEXT, PRIMARY KEY(run_id,contract_id,line_id));
CREATE TABLE IF NOT EXISTS findings(run_id TEXT, contract_id TEXT, line_id TEXT, classification TEXT,
 expected_pence INTEGER, discrepancy_pence INTEGER, requires_review INTEGER, result_json TEXT,
 PRIMARY KEY(run_id,contract_id,line_id));
'''


def run(data_root: Path, db_path: Path, report_path: Path) -> dict:
    folders = sorted(p for p in data_root.iterdir() if p.is_dir() and (p/'contract.pdf').is_file())
    if not folders: raise ValueError('No contractor folders found')
    prepared=[]; ids=set()
    for folder in folders:
        terms,visits,lines,sources=load_scenario(folder)
        if terms['contract_id'] in ids: raise ValueError('Duplicate contract identifier across folders')
        ids.add(terms['contract_id'])
        results=reconcile(terms,visits,lines)
        prepared.append((folder,terms,visits,lines,sources,results))
    report=dict(schema_version='1.0',run_id=str(uuid.uuid4()),created_at=datetime.now(timezone.utc).isoformat(),
                currency='GBP',money_unit='integer_pence',tax_basis='exclusive_of_vat',
                scope='Controlled synthetic contracts only. Findings require review; not payment instructions.',contracts=[])
    db_path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute('PRAGMA foreign_keys=ON'); db.executescript(SCHEMA)
        db.execute('INSERT INTO runs VALUES (?,?)',(report['run_id'],report['created_at']))
        for folder,t,visits,lines,sources,results in prepared:
            key=(report['run_id'],t['contract_id'])
            db.execute('INSERT INTO contracts VALUES (?,?,?)',(*key,json.dumps(t)))
            db.executemany('INSERT INTO sources VALUES (?,?,?,?)',[(*key,s['file'],s['sha256']) for s in sources])
            db.executemany('INSERT INTO visits VALUES (?,?,?,?,?)',[(*key,v['job_id'],v['status'],json.dumps(v)) for v in visits])
            db.executemany('INSERT INTO invoice_lines VALUES (?,?,?,?,?,?,?)',[(*key,l['invoice_id'],l['line_id'],l['job_id'],l['line_amount_pence'],json.dumps(l)) for l in lines])
            db.executemany('INSERT INTO findings VALUES (?,?,?,?,?,?,?,?)',[(*key,r['line_id'],r['classification'],r['expected_pence'],r['discrepancy_pence'],int(r['requires_review']),json.dumps(r)) for r in results])
            report['contracts'].append(dict(contract_id=t['contract_id'],contractor=t['contractor'],scenario_folder=folder.name,sources=sources,summary=summarize(results),lines=results))
    report['summary']=summarize([r for c in report['contracts'] for r in c['lines']])
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    return report


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=ROOT/'Data'/'Contracts')
    parser.add_argument('--database',type=Path,default=ROOT/'output'/'reconciliation.sqlite3')
    parser.add_argument('--report',type=Path,default=ROOT/'output'/'reconciliation.json')
    args=parser.parse_args()
    try: report=run(args.data.resolve(),args.database.resolve(),args.report.resolve())
    except (ValueError,OSError,sqlite3.Error) as exc: parser.exit(1,f'Reconciliation failed: {exc}\n')
    s=report['summary']
    print(f"Checked {len(report['contracts'])} contracts and {s['invoice_line_count']} invoice lines.")
    print(f"Review: {s['flagged_line_count']} lines; unverifiable: {s['unverified_line_count']}.")
    print(f"Known discrepancy: GBP {s['known_discrepancy_total_pence']/100:.2f}. Realised savings: GBP 0.00.")
    print(f'Database: {args.database}\nReport: {args.report}')


if __name__=='__main__': main()
