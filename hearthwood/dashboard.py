"""Manager overview computed from actual stored records, without invented KPIs."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from .reporting import build_report


def build_dashboard(cases, source='interactive', now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    pending = [c for c in cases if c['status'] == 'pending']

    def age(case):
        try:
            created = datetime.fromisoformat(case['created_at'])
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return max(0, (now-created).total_seconds()/3600)
        except (KeyError, ValueError, TypeError):
            return None

    urgent = [c for c in pending if c['result']['urgency'] == 'urgent']
    aged = [c for c in pending if age(c) is not None and age(c) >= 24]
    uncertain = [c for c in pending if c['result']['uncertain']]
    priority = {'urgent': 0, 'normal': 1, 'low': 2}
    attention = sorted(pending, key=lambda c: (priority[c['result']['urgency']], -(age(c) or 0)))[:8]
    report = build_report(cases)
    end = datetime.fromisoformat(report['period_end']).date()
    dates = [(end-timedelta(days=i)).isoformat() for i in reversed(range(14))]
    daily = Counter(c['complaint'].get('date', c['created_at'][:10]) for c in cases)
    products = Counter(c['complaint'].get('product') or 'Not specified' for c in cases)
    brief = []
    for title, rows, action in [
        ('Urgent cases awaiting review', urgent, 'Review the source and contact the responsible team.'),
        ('Cases awaiting review for 24+ hours', aged, 'Check the oldest cases and assign a reviewer outside this tool.'),
        ('Cases needing clarification', uncertain, 'Confirm missing details before approving the reply.')]:
        if rows:
            brief.append({'title': title, 'count': len(rows), 'action': action,
                          'case_ids': [c['id'] for c in rows]})
    return {
        'source': source, 'generated_at': now.isoformat(), 'total': len(cases),
        'pending': len(pending), 'urgent_pending': len(urgent), 'aged_pending': len(aged),
        'uncertain_pending': len(uncertain),
        'approved': sum(c['status']=='approved' for c in cases),
        'rejected': sum(c['status']=='rejected' for c in cases),
        'brief': brief,
        'attention': [{'id': c['id'], 'customer': c['complaint'].get('customer') or 'Customer not specified',
                       'product': c['complaint'].get('product') or 'Not specified',
                       'category': c['result']['category'], 'urgency': c['result']['urgency'],
                       'team': c['result']['team'], 'age_hours': round(age(c),1) if age(c) is not None else None}
                      for c in attention],
        'products': [{'name': name, 'count': count} for name,count in products.most_common(5)],
        'daily': [{'date': day, 'count': daily[day]} for day in dates],
        'report': report,
        'note': 'Review status is not customer resolution. Age is time since intake, not an agreed SLA.'}
