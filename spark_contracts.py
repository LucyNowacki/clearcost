"""Extract one contract through ChatGPT-authenticated Codex Spark."""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from llm_contracts import document, validate, SCHEMA, FIELDS, INSTRUCTIONS, ROOT

MODEL = 'gpt-5.3-codex-spark'
VERSION = 'spark-contract-v2'


def extract_spark(path, output_dir=ROOT/'output'/'llm'):
    doc = document(path)
    env = dict(os.environ)
    for key in ['OPENAI_API_KEY','CODEX_API_KEY']:
        env.pop(key, None)
    status = subprocess.run(['codex','login','status'],env=env,capture_output=True,text=True,timeout=15)
    if status.returncode or 'Logged in using ChatGPT' not in status.stdout+status.stderr:
        raise ValueError('Codex ChatGPT sign-in is required. No API-key fallback will be used.')
    prompt = INSTRUCTIONS+'\nUse only the supplied text. Do not use tools or access files. Quotes must be exact contiguous copied substrings. Do not join separated sentences or correct punctuation. Use one short sufficient quote per field; mention other conditions in the value.\n'+json.dumps({
        'requested_fields':FIELDS,'pages':[{'page':i+1,'text':p} for i,p in enumerate(doc['pages'])]})
    cache_key = hashlib.sha256((VERSION+MODEL+doc['sha256']+prompt).encode()).hexdigest()
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    target=output_dir/(cache_key+'.json')
    if target.exists():return target
    with tempfile.TemporaryDirectory(prefix='fuse-spark-') as d:
        schema=Path(d)/'schema.json';schema.write_text(json.dumps(SCHEMA))
        result=Path(d)/'result.json'
        command=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check',
                 '--sandbox','read-only','--model',MODEL,'-c','model_reasoning_effort="low"',
                 '--output-schema',str(schema),'--output-last-message',str(result),'-']
        try:
            run=subprocess.run(command,input=prompt,env=env,cwd=d,capture_output=True,text=True,timeout=180)
        except subprocess.TimeoutExpired:
            raise ValueError('Spark extraction timed out. No automatic retry was made.') from None
        if run.returncode or not result.exists():
            # Report a bounded diagnostic, never authentication data.
            raise ValueError('Codex Spark failed to produce a draft. Check model access or usage limits.')
        raw=json.loads(result.read_text())
        try:
            extraction=validate(raw,doc['pages'])
        except ValueError:
            rejected=output_dir/'rejected';rejected.mkdir(exist_ok=True)
            (rejected/(cache_key+'.json')).write_text(json.dumps(raw,indent=2))
            raise
    draft={'status':'draft_needs_human_review','model':MODEL,'version':VERSION,
           'provider':'codex_chatgpt','source':doc['path'],'source_sha256':doc['sha256'],
           'created_at':datetime.now(timezone.utc).isoformat(),'extraction':extraction,
           'validation':'Field structure and quoted text checked; meaning requires human review.'}
    temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(draft,indent=2));temporary.replace(target)
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('document',type=Path)
    args=parser.parse_args()
    try:print(extract_spark(args.document))
    except (ValueError,OSError,subprocess.SubprocessError) as exc:parser.exit(1,str(exc)+'\n')
