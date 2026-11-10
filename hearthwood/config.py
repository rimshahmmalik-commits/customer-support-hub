"""Paths and settings. No account keys belong in source control."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ['Oslo 3-seater sofa', 'Malmo wardrobe', 'Kensington dining table',
            'Nordic bed frame', 'Halden bookcase', 'Avery armchair', 'Linden desk', 'Brisk coffee table']
COURIER_SHARE = {'SwiftDrop': 0.6, 'ParcelPath': 0.4}
CATEGORIES = ('product_safety', 'damaged_item', 'late_delivery', 'missing_parts',
              'wrong_item', 'refund_delay', 'assembly_help', 'unclear')
TEAMS = {'product_safety': 'Product Safety', 'damaged_item': 'Returns & Claims',
         'late_delivery': 'Delivery Support', 'missing_parts': 'Parts Dispatch',
         'wrong_item': 'Fulfilment', 'refund_delay': 'Finance (Refunds)',
         'assembly_help': 'Customer Care', 'unclear': 'General Support'}


def load_env():
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
                continue
            name, value = line.split('=', 1)
            name = name.strip()
            if name in {'OPENAI_API_KEY', 'OPENAI_MODEL', 'HEARTHWOOD_PORT',
                        'SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD','SMTP_FROM'} or name.startswith('TEAM_EMAIL_'):
                os.environ.setdefault(name, value.strip().strip('\"\''))


def database_path():
    return Path(os.getenv('HEARTHWOOD_DB', ROOT / 'runtime/hearthwood.sqlite3'))
