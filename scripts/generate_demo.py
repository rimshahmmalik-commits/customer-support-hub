"""Step 1: create realistic, messy customer complaints for the fictional store 'Hearthwood Home'.
Hidden patterns are planted on purpose so the root-cause report has a pattern to investigate; they are not real business findings."""
import csv, random
from pathlib import Path
from datetime import date, timedelta
random.seed(42)
TODAY = date(2026, 11, 9)

COURIER_SHARE = {"SwiftDrop": 0.6, "ParcelPath": 0.4}   # share of ALL orders each courier carries
BULKY = ["Oslo 3-seater sofa", "Malmo wardrobe", "Kensington dining table", "Nordic bed frame"]
SMALL = ["Halden bookcase", "Avery armchair", "Linden desk", "Brisk coffee table"]
NAMES = ["Priya Shah", "Tom Becker", "Aisha Khan", "Liam O'Connor", "Sofia Rossi", "Daniel Wright",
         "Hannah Meyer", "Omar Farouk", "Chloe Bennett", "Jack Turner", "Maya Patel", "Ben Harris",
         "Emma Clarke", "Noah Evans", "Zara Ahmed", "Luke Foster", "Grace Liu", "Sam Walker"]

T = {
 "damaged_item": [
  "My {p} arrived with a huge crack down one side. Order {o}. Not happy at all.",
  "box was crushed when the driver dropped it off and the {p} is badly scratched, order {o}",
  "The {p} has been damaged in transit - one panel is snapped. Order number {o}. What are you going to do about it?",
  "Opened my {p} today and the corner is smashed. I want this sorted. {o}"],
 "late_delivery": [
  "My {p} was meant to arrive on Tuesday and there is still no sign of it. Order {o}.",
  "Still waiting for my {p}!! it's been over two weeks and tracking hasn't moved. {o}",
  "Delivery is really late. Where is my {p}? Order {o}",
  "The courier keeps rescheduling and I've been waiting in all week for the {p}. Order {o}."],
 "missing_parts": [
  "The {p} arrived but there is no bag of screws in the box so I can't build it. Order {o}.",
  "Parts missing from my {p} - only 3 of the 4 legs were in the box. {o}",
  "Hi, the fittings for the {p} aren't in the box. Order {o}. Can you send them?",
  "I've unpacked everything and we're short of two side panels for the {p}. Ref {o}"],
 "wrong_item": [
  "I ordered the {p} but you've sent a different colour. Order {o}.",
  "This isn't what I ordered. I paid for the {p} and got something else entirely. {o}",
  "Wrong item delivered, I ordered the {p} in oak and this is walnut. {o}"],
 "refund_delay": [
  "I returned my {p} three weeks ago and I still haven't been refunded. Order {o}.",
  "Where is my money back? Returned the {p} and nothing has hit my account. {o}",
  "You've confirmed my refund for the {p} twice now but I'm still waiting on the money. Order {o}."],
 "assembly_help": [
  "Quick question about the {p}, the instructions don't make sense at step 6. How do I attach the back panel? Order {o}",
  "Can someone help me put together the {p}? I can't work out which way the shelves go. {o}"],
}
VAGUE = ["this is unacceptable", "Hello?? is anyone there. I've sent three messages",
         "my order is a mess", "Very disappointed. Sort it out please."]
URGENT_EXTRAS = ["It's a wedding gift and the wedding is on Saturday.", "We're moving house this weekend so I really need this.",
                 "This is the third time I've had to contact you.", "We have a newborn arriving next week and this is for the nursery.",
                 "If it isn't fixed I'll go to my bank."]
ANGRY_EXTRAS = ["Absolutely disgusting service.", "This is ridiculous!!", "Honestly furious.", "Worst experience I've had online."]

# how many of each kind (75 total). Mixed = two problems in one message.
PLAN = [("damaged_item", 18), ("late_delivery", 14), ("missing_parts", 12), ("wrong_item", 6),
        ("refund_delay", 10), ("assembly_help", 5), ("vague", 4)]
MIXED = [("damaged_item", "refund_delay"), ("late_delivery", "refund_delay"), ("missing_parts", "assembly_help")] * 2

def pick_courier(cat):
    pp = {"damaged_item": 0.70, "late_delivery": 0.60}.get(cat, COURIER_SHARE["ParcelPath"])  # planted pattern
    return "ParcelPath" if random.random() < pp else "SwiftDrop"

def pick_product(cat):
    if cat == "damaged_item":                                   # planted: bulky items break more
        return random.choice(BULKY) if random.random() < 0.75 else random.choice(SMALL)
    if cat == "missing_parts" and random.random() < 0.65:       # planted: one supplier packing issue
        return random.choice(["Malmo wardrobe", "Nordic bed frame"])
    return random.choice(BULKY + SMALL)

def pick_date(cat, courier):
    if cat == "damaged_item" and courier == "ParcelPath" and random.random() < 0.7:
        return TODAY - timedelta(days=random.randint(0, 13))    # planted: damage from ParcelPath is rising
    return TODAY - timedelta(days=random.randint(0, 27))

def roughen(text):
    if random.random() < 0.25:
        text = text.lower().rstrip(".")
    return text

rows = []
jobs = [(c, None) for c, n in PLAN for _ in range(n)] + [(a, b) for a, b in MIXED]
for cat, second in jobs:
    courier, product = pick_courier(cat), pick_product(cat)
    order = f"HW-{random.randint(10000, 99999)}"
    if cat == "vague":
        msg = random.choice(VAGUE)
        if random.random() < 0.5: msg += f" {order}"
    else:
        msg = random.choice(T[cat]).format(p=product, o=order)
        if second:
            nxt = random.choice(T[second]).format(p=product, o=order)
            msg += " Also, " + nxt[0].lower() + nxt[1:]
    if random.random() < 0.20: msg += " " + random.choice(URGENT_EXTRAS)
    if random.random() < 0.25: msg += " " + random.choice(ANGRY_EXTRAS)
    rows.append({"date": pick_date(cat, courier).isoformat(), "customer": random.choice(NAMES), "order_id": order,
                 "product": product, "courier": courier, "message": roughen(msg),
                 "true_category": cat + (f"|{second}" if second else "")})

rows.sort(key=lambda r: r["date"])
for i, r in enumerate(rows, 1): r["id"] = f"C{i:03d}"
cols = ["id", "date", "customer", "order_id", "product", "courier", "message", "true_category"]
target = Path(__file__).resolve().parents[1] / "data/generated-complaints.csv"
with target.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows({c: r[c] for c in cols} for r in rows)
print(f"wrote {len(rows)} synthetic complaints to {target}; original data unchanged")

