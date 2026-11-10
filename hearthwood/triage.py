"""Transparent rule baseline, output validation and policy-controlled reply drafts."""
import re
from .config import CATEGORIES, TEAMS

RULE_VERSION = 'hearthwood-rules-2'
KEYWORDS = {
    'damaged_item': ['crack', 'scratch', 'dent', 'smash', 'damag', 'broken', 'snapped', 'split', 'chip', 'crushed', 'in pieces'],
    'late_delivery': ['late', 'delay', 'still waiting', 'not arrived', 'no sign', 'been waiting', 'where is my', 'tracking', 'rescheduling'],
    'missing_parts': ['missing', 'no bag of', 'short of', 'only 3', 'only two', 'fittings', 'not in the box', "aren't in the box"],
    'wrong_item': ['wrong item', 'wrong colour', 'wrong color', 'what i ordered', 'different colour', 'different color', 'something else entirely'],
    'refund_delay': ['refund', 'money back', 'waiting on the money', 'hit my account'],
    'assembly_help': ['assemble', 'assembly', 'instructions', 'put together', 'how do i', 'which way'],
}
SAFETY = re.compile(r'\b(injur\w*|hurt|bleeding|electric(?:al)? shock|electrocut\w*|smok\w*|fire|burn(?:ed|t|ing|s)?|collapsed|tipped over|fell (?:onto|on)\b|trapped|choking)\b', re.I)
URGENT = re.compile(r'\b(wedding|moving house|third time|newborn|my bank|solicitor|trading standards)\b', re.I)
ANGRY = re.compile(r'\b(disgusting|ridiculous|unacceptable|worst|furious)\b|!!|not happy at all', re.I)


def validate_input(row):
    if not isinstance(row, dict):
        raise ValueError('Expected a JSON object.')
    clean = {}
    for name, limit in [('message', 8000), ('customer', 100), ('product', 100), ('courier', 50), ('order_id', 60), ('customer_email',254)]:
        value = row.get(name, '')
        if not isinstance(value, str):
            raise ValueError(f'{name} must be text.')
        value = value.strip()
        if len(value) > limit:
            raise ValueError(f'{name} exceeds {limit} characters.')
        clean[name] = value
    if not clean['message']:
        raise ValueError('Please enter the customer complaint.')
    if clean['customer_email']:
        from .messaging import valid_email
        if not valid_email(clean['customer_email']):
            raise ValueError('Enter a valid customer email address.')
    return clean


def safety_evidence(message):
    hits = []
    for match in SAFETY.finditer(message):
        before = message[max(0, match.start()-30):match.start()].lower()
        # Explicit denials are not positive evidence. Broader ambiguity still needs review.
        if re.search(r'\b(no|not|without|isn\x27t|wasn\x27t|nobody|no one)(?:\s+\w+){0,2}\s*$', before):
            continue
        hits.append(message[max(0, match.start()-25):min(len(message), match.end()+45)])
    return list(dict.fromkeys(hits))[:3]


def positive_occurrences(text, keyword):
    result = []
    for match in re.finditer(re.escape(keyword), text, re.I):
        if match.start() > 0 and text[match.start()-1].isalnum():
            continue  # e.g. 'late' inside 'plate'
        before = text[max(0, match.start()-28):match.start()].lower()
        # Missing-part and wrong-item cues sometimes express absence themselves.
        if keyword not in {'not arrived', 'not in the box', "aren't in the box", 'no bag of', 'what i ordered'} and re.search(r'\b(not|isn\x27t|wasn\x27t|is not|was not|without)(?:\s+(?:at all|actually|even|badly))?\s*$', before):
            continue
        result.append((match.start(), match.end()))
    return result


def classify_rules(row):
    row = validate_input(row)
    message = row['message']
    matches = {category: [span for keyword in words for span in positive_occurrences(message, keyword)]
               for category, words in KEYWORDS.items()}
    # Waiting for a refund is not late delivery. Retain delivery only if it is explicit too.
    if matches['refund_delay'] and not re.search(r'\b(deliver\w*|courier|tracking|parcel|shipment|arriv\w*)\b', message, re.I):
        matches['late_delivery'] = []
    hits = sorted([c for c in matches if matches[c]], key=lambda c: (-len(matches[c]), list(KEYWORDS).index(c)))
    category = hits[0] if hits else 'unclear'
    evidence = []
    for c in hits[:3]:
        start, end = matches[c][0]
        evidence.append(message[max(0, start-20):min(len(message), end+45)])
    safety = safety_evidence(message)
    uncertain = category == 'unclear' or len(hits) > 1 or len(message.split()) < 4
    reason = ('The message does not identify a specific issue.' if category == 'unclear'
              else 'More than one issue is mentioned; check the primary route.' if len(hits) > 1
              else 'A short message gives limited context.' if uncertain
              else 'Matched explicit wording in the complaint. Check before using the draft.')
    return apply_policy({'category': category, 'secondary': hits[1:],
        'urgency': 'urgent' if URGENT.search(message) else 'low' if category == 'assembly_help' and not ANGRY.search(message) else 'normal',
        'sentiment': 'angry' if ANGRY.search(message) else 'neutral',
        'summary': message[:240], 'evidence': evidence or [message],
        'uncertain': uncertain, 'reason': reason, 'safety_flag': bool(safety)}, row,
        engine='Keyword rules', model=RULE_VERSION)


def validate_model_output(data, message):
    fields = {'category','secondary','urgency','sentiment','summary','evidence','uncertain','reason','safety_flag'}
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError('The AI returned missing or unexpected fields.')
    if data['category'] not in CATEGORIES:
        raise ValueError('The AI returned an unknown category.')
    if not isinstance(data['secondary'], list) or any(x not in CATEGORIES for x in data['secondary']):
        raise ValueError('The AI returned invalid secondary categories.')
    if data['urgency'] not in ('urgent','normal','low') or data['sentiment'] not in ('angry','neutral','distressed'):
        raise ValueError('The AI returned an invalid priority or sentiment.')
    if type(data['uncertain']) is not bool or type(data['safety_flag']) is not bool:
        raise ValueError('The AI returned an invalid review flag.')
    for field in ('summary','reason'):
        if not isinstance(data[field], str) or not 1 <= len(data[field]) <= 1500:
            raise ValueError(f'The AI returned invalid {field}.')
    if not isinstance(data['evidence'], list) or not 1 <= len(data['evidence']) <= 5:
        raise ValueError('The AI must provide one to five exact complaint quotes.')
    if any(not isinstance(q,str) or not q.strip() or q not in message for q in data['evidence']):
        raise ValueError('An AI evidence quote does not occur in the original complaint.')
    return data


def draft_reply(row, category):
    # These are proposed next steps, not claims that other systems have acted.
    first = (row.get('customer') or 'there').split()[0]
    intro = "Thanks for getting in touch. I'm sorry there's a problem with your order."
    body = {
        'product_safety': "Thank you for reporting this. Please stop using the affected item and keep others away from it. This needs a product-safety review. If anyone is in immediate danger, contact the appropriate emergency services. Could you share your order number and, only if it is safe, a brief description of what happened?",
        'damaged_item': "Could you share your order number and photos of the damage and packaging, if available? A team member can then review the appropriate next steps with you.",
        'late_delivery': "Could you confirm your order number and the latest tracking update? Our delivery team can review the status and advise on the next step. A delivery date still needs to be confirmed.",
        'missing_parts': "Could you share your order number and identify the missing parts using the assembly guide, if possible? The parts team can check what is needed and confirm availability before arranging anything.",
        'wrong_item': "Could you share your order number and a photo or description of the item received? The fulfilment team can check this against your order and confirm the available options.",
        'refund_delay': "Could you confirm your order number, return date and any refund reference? The finance team can check the refund status. I cannot confirm a payment date until that check is complete.",
        'assembly_help': "Could you tell us which step is unclear and confirm the product and order number? A team member can check the relevant instructions with you. Please pause assembly if anything appears unsafe.",
        'unclear': "Could you share your order number and explain what has gone wrong? That will help us identify the right team and avoid making assumptions.",
    }[category]
    if row.get('order_id'):
        intro += f" This relates to order {row['order_id']}."
        body = (body.replace('share your order number and, only if it is safe,', 'share, only if it is safe,')
                    .replace('share your order number and photos', 'share photos')
                    .replace('confirm your order number and the latest', 'share the latest')
                    .replace('share your order number and identify', 'identify')
                    .replace('share your order number and a photo', 'share a photo')
                    .replace('confirm your order number, return date and any', 'confirm the return date and any')
                    .replace('confirm the product and order number', 'confirm the product')
                    .replace('share your order number and explain', 'explain'))
    return f'Hi {first},\n\n{intro}\n\n{body}\n\nKind regards,\nHearthwood Customer Care'


def apply_policy(data, row, engine, model):
    result = dict(data)
    result['secondary'] = list(dict.fromkeys(x for x in data['secondary'] if x != data['category']))
    safety = safety_evidence(row['message'])
    if safety or data['safety_flag'] or data['category'] == 'product_safety':
        if data['category'] != 'product_safety' and data['category'] != 'unclear':
            result['secondary'] = list(dict.fromkeys([data['category']] + result['secondary']))
        result.update(category='product_safety', urgency='urgent', safety_flag=True, uncertain=True,
                      reason='Possible product-safety issue. Escalate for human review; do not treat this as a routine claim.')
        result['evidence'] = list(dict.fromkeys(safety + data['evidence']))[:5]
    if result['category'] == 'unclear':
        result.update(uncertain=True, urgency='normal' if result['urgency']=='low' else result['urgency'])
    if result['uncertain'] and result['urgency'] == 'low':
        result['urgency'] = 'normal'
    result.update(team=TEAMS[result['category']], engine=engine, model=model,
                  draft=draft_reply(row, result['category']), human_review_required=True,
                  fallback_reason=None)
    return result


def draft_issues(text):
    """A limited guardrail, not a claim that arbitrary human edits are safe."""
    issues = []
    if re.search(r"\b(we(?:'re| are) sending|we(?:'ve| have) (?:sent|asked|issued|processed|arranged)|i(?:'ve| have) (?:sent|issued|processed)|refund (?:has been|is) (?:issued|processed)|guarantee)\b", text, re.I):
        issues.append('The draft claims an action or guarantee that this app cannot verify. Reword it as a proposed next step.')
    return issues
