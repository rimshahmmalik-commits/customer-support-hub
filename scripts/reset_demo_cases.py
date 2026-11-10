"""Explicitly replace submitted cases with synthetic examples; preserve training and credentials."""
import argparse
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sqlite3
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hearthwood.config import database_path,load_env
from hearthwood.triage import validate_input,classify_rules


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace-submitted',action='store_true',required=True)
    parser.parse_args()
    load_env();path=database_path()
    if not path.is_file():raise SystemExit('Start the app once before resetting its demo cases.')
    fixture=json.loads((ROOT/'data/demo_cases.json').read_text(encoding='utf-8'))
    now=datetime.now(timezone.utc);prepared=[]
    for index,item in enumerate(fixture['cases'],1):
        complaint=validate_input(item);result=classify_rules(complaint)
        if result['category']!=item['expected_category']:
            raise SystemExit(f'Fixture {index} did not reach its expected category; no records changed.')
        created=(now-timedelta(hours=item['age_hours'])).isoformat(timespec='seconds')
        complaint.update(synthetic=True,date=created[:10])
        prepared.append((f'HW-DEMO-{index:03d}',created,complaint,result))
    backup_dir=path.parent/'backups';backup_dir.mkdir(exist_ok=True)
    backup=backup_dir/('before-demo-reset-'+now.strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]+'.sqlite3')
    with sqlite3.connect(path,timeout=15) as con:
        active=con.execute("SELECT count(*) FROM outbox WHERE state='submitting'").fetchone()[0]
        if active:raise SystemExit('An email attempt is in progress. No records changed.')
        with sqlite3.connect(backup) as destination:con.backup(destination)
        con.execute('BEGIN IMMEDIATE')
        removed=con.execute("SELECT count(*) FROM cases WHERE source='interactive'").fetchone()[0]
        # Remove related case records, not global connection/audit events or training data.
        for table in ('attachments','outbox','audit'):
            con.execute(f"DELETE FROM {table} WHERE case_id IN (SELECT id FROM cases WHERE source='interactive')")
        con.execute("DELETE FROM cases WHERE source='interactive'")
        for case_id,created,complaint,result in prepared:
            con.execute('INSERT INTO cases(id,created_at,source,complaint,result,original_result,status) VALUES (?,?,?,?,?,?,?)',
                (case_id,created,'interactive',json.dumps(complaint),json.dumps(result),json.dumps(result),'pending'))
            con.execute('INSERT INTO audit(at,case_id,action,details) VALUES (?,?,?,?)',
                (now.isoformat(timespec='seconds'),case_id,'synthetic_demo_case_created',json.dumps({
                    'engine':result['engine'],'category':result['category'],'synthetic':True,
                    'intake_timestamp':'Fictional demo date','review_status':'Pending; no review or email fabricated'})))
        con.execute('INSERT INTO audit(at,case_id,action,details) VALUES (?,?,?,?)',
            (now.isoformat(timespec='seconds'),None,'demo_workspace_reset',json.dumps({
                'removed_submitted_cases':removed,'added_synthetic_cases':len(prepared),'training_preserved':True})))
    print(f'Replaced {removed} submitted cases with {len(prepared)} fictional pending complaints.')
    print(f'Backup: {backup}')
    print('Training data and connection settings preserved. No emails sent.')


if __name__=='__main__':main()
