"""Descriptive signals with source records, not causal conclusions."""
from collections import Counter
from datetime import date, timedelta
from .config import COURIER_SHARE


def build_report(cases, as_of=None):
    dated = []
    for case in cases:
        try:
            day = date.fromisoformat(case['complaint'].get('date',case['created_at'][:10]))
        except (ValueError,KeyError,TypeError):
            continue
        dated.append((day,case))
    end = date.fromisoformat(as_of) if as_of else max((d for d,_ in dated),default=date.today())
    start = end-timedelta(days=27)
    window = [(day,case) for day,case in dated if start<=day<=end]
    counts = Counter(case['result']['category'] for _,case in window)
    insights = []
    for category in ('damaged_item','late_delivery'):
        subset = [case for _,case in window if case['result']['category']==category]
        if not subset:
            continue
        for courier,order_share in COURIER_SHARE.items():
            linked = [c for c in subset if c['complaint'].get('courier')==courier]
            share = len(linked)/len(subset)
            if len(linked)>=3 and share/order_share>=1.3:
                insights.append({'title':f'{courier} · {category.replace("_"," ")}',
                    'observation':f'{len(linked)} of {len(subset)} complaints in this category ({share:.0%}) mention {courier}, compared with its assumed {order_share:.0%} overall order share.',
                    'hypothesis':'This is a signal for investigation, not proof of courier fault.',
                    'next_step':'Compare damaged/delayed shipments with all shipments, split by product size, route and week. Request handling records.',
                    'evidence_ids':[c['id'] for c in linked],
                    'caveat':'Overall order shares are scenario assumptions. Shipment-level counts and product mix are unavailable.'})
    parts = [case for _,case in window if case['result']['category']=='missing_parts']
    products = Counter(c['complaint'].get('product','Unknown') for c in parts)
    top = products.most_common(2)
    if len(parts)>=3 and top and sum(n for _,n in top)/len(parts)>=0.5:
        names = [p for p,_ in top]
        linked = [c for c in parts if c['complaint'].get('product') in names]
        insights.append({'title':'Missing-parts product cluster',
            'observation':f'{" and ".join(names)} account for {len(linked)} of {len(parts)} missing-parts complaints.',
            'hypothesis':'Packing or assembly-kit issues are possibilities to check, not established causes.',
            'next_step':'Compare missing-part reports against units sold, packing batches and supplier inspection records.',
            'evidence_ids':[c['id'] for c in linked],
            'caveat':'Without product-level sales and batch records, complaint counts do not establish defect rates.'})
    recent_start = end-timedelta(days=13)
    damage_recent = [c for day,c in window if day>=recent_start and c['result']['category']=='damaged_item']
    damage_before = [c for day,c in window if day<recent_start and c['result']['category']=='damaged_item']
    return {'period_start':start.isoformat(),'period_end':end.isoformat(),'total':len(window),
        'excluded':len(cases)-len(window),'categories':dict(counts),
        'urgent':sum(c['result']['urgency']=='urgent' for _,c in window),
        'safety':sum(c['result']['safety_flag'] for _,c in window),
        'insights':insights,
        'damage_trend':{'recent_14_days':len(damage_recent),'previous_14_days':len(damage_before),
            'evidence_ids':[c['id'] for c in damage_recent+damage_before]},
        'note':'Primary classifications only. Counts are not shipment-adjusted rates. Courier shares are assumptions; signals do not establish a cause.'}


def report_markdown(report):
    text = ['# Customer Support Hub: complaint investigation',
        'Demo business: Hearthwood Home, fictional furniture store.',
        f'{report["period_start"]} to {report["period_end"]} · {report["total"]} complaints',
        '',report['note'],'','## Primary complaint categories']
    for category,count in sorted(report['categories'].items(),key=lambda x:-x[1]):
        text.append(f'- {category.replace("_"," ")}: {count}')
    if not report['total']:
        text.append('No complaints in the selected window.')
    text+=['','## Investigation signals']
    for signal in report['insights']:
        text += ['',f'### {signal["title"]}',signal['observation'],signal['hypothesis'],
                 'Next check: '+signal['next_step'],'Limits: '+signal['caveat'],
                 'Complaint references: '+', '.join(signal['evidence_ids'])]
    if not report['insights']:
        text.append('No cluster met the simple investigation threshold. That does not prove there are no problems.')
    trend=report['damage_trend']
    text += ['',f'Damage complaints: {trend["recent_14_days"]} in the recent 14 days; {trend["previous_14_days"]} in the preceding 14 days.',
             'These are counts, not shipment-adjusted damage rates.']
    return '\n'.join(text)
