"""Suggest only details visible in a reviewed transcript; never fill the form silently."""
import re
from .config import PRODUCTS
from .messaging import valid_email


def suggest_details(text):
    if not isinstance(text,str) or not text.strip() or len(text)>8000:
        raise ValueError('Provide extracted complaint text, up to 8,000 characters.')
    fields={name:{'value':'','evidence':'','note':'Not found clearly. Leave unchanged or enter it manually.'}
            for name in ('customer','customer_email','order_id','product')}
    senders=list(re.finditer(r'^\s*From:\s*([^\n<>]{1,100}?)\s*<([^<>\n]+)>\s*$',text,re.I|re.M))
    identities={(m[1].strip(),m[2].strip()) for m in senders if valid_email(m[2].strip())}
    if len(identities)==1:
        name,email=next(iter(identities));evidence=next(m[0].strip() for m in senders if m[2].strip()==email)
        fields['customer']={'value':name,'evidence':evidence,'note':'From the visible sender header.'}
        fields['customer_email']={'value':email,'evidence':evidence,'note':'From the visible sender header. Confirm before sending.'}
    elif len(identities)>1:
        for key in ('customer','customer_email'):
            fields[key]['note']='Multiple senders found. Choose the correct customer manually.'
    else:
        # Only use an explicitly labelled customer name; never guess from prose/signatures.
        named=re.findall(r'^\s*Customer(?: name)?:\s*([^\n<>]{1,100})\s*$',text,re.I|re.M)
        if len(set(n.strip() for n in named))==1:
            value=named[0].strip();fields['customer']={'value':value,'evidence':value,'note':'From the visible customer label.'}
    orders=list(re.finditer(r'\bHW-\d{3,10}\b',text,re.I))
    unique_orders={m[0].upper() for m in orders}
    if len(unique_orders)==1:
        fields['order_id']={'value':next(iter(unique_orders)),'evidence':orders[0][0],'note':'One distinct Hearthwood order reference found.'}
    elif len(unique_orders)>1:
        fields['order_id']['note']='Multiple order references found. Select the correct order manually.'
    products=[p for p in PRODUCTS if re.search(r'(?<!\w)'+re.escape(p)+r'(?!\w)',text,re.I)]
    if len(products)==1:
        value=products[0];match=re.search(re.escape(value),text,re.I)
        fields['product']={'value':value,'evidence':match[0],'note':'Matches a product in the configured catalogue.'}
    elif len(products)>1:
        fields['product']['note']='Multiple catalogue products found. Select the affected product manually.'
    return {'fields':fields,'review_required':True,
            'note':'Suggestions are derived from visible text, not verified customer or order records. Confirm before applying.'}
