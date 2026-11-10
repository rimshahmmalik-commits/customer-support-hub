"""Reproducible offline development evaluation. No paid API calls."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hearthwood.triage import classify_rules


def main():
    with (ROOT / 'data/complaints.csv').open(encoding='utf-8') as source:
        original = list(csv.DictReader(source))
    with (ROOT / 'data/challenge.json').open(encoding='utf-8') as source:
        challenge = json.load(source)
    results = {}
    for name, rows in [('original_generated', original), ('challenge', challenge)]:
        records = []
        for row in rows:
            labels = [('unclear' if label == 'vague' else label)
                      for label in row['true_category'].split('|')]
            result = classify_rules({'message': row['message']})
            predicted = {result['category'], *result['secondary']}
            records.append({'id': row['id'], 'message': row['message'], 'expected': labels,
                            'predicted': sorted(predicted), 'primary': result['category'],
                            'primary_matches_any_label': result['category'] in labels,
                            'exact_label_set': predicted == set(labels),
                            'uncertain': result['uncertain']})
        results[name] = {'count': len(records),
            'primary_matches_any_label': sum(r['primary_matches_any_label'] for r in records),
            'exact_label_set': sum(r['exact_label_set'] for r in records),
            'records': records}
    target = ROOT / 'docs/evaluation-results.json'
    target.write_text(json.dumps(results, indent=2), encoding='utf-8')
    for name, result in results.items():
        print(f"{name}: primary-in-labels {result['primary_matches_any_label']}/{result['count']}; exact labels {result['exact_label_set']}/{result['count']}")
        for row in result['records']:
            if not row['exact_label_set']:
                print(f"  {row['id']}: expected {row['expected']}; predicted {row['predicted']}")
    print('Development data, not independent evidence of real-world accuracy. OpenAI not evaluated here.')


if __name__ == '__main__':
    main()
