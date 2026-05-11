import requests, time, json

now = int(time.time())
rounded = (now // 300) * 300
utc_now = time.strftime("%H:%M:%S", time.gmtime(now))
print(f"Now: {now}, Rounded: {rounded}, UTC: {utc_now}")

# Check slug formats
formats = [
    "btc-updown-5m-{ts}",
    "btc-up-or-down-5m-{ts}",
    "btc-up-or-down-5min-{ts}",
    "btc-minute-5-{ts}",
]
for fmt in formats:
    for offset in [0, -300, 300]:
        slug = fmt.format(ts=rounded + offset)
        r = requests.get("https://gamma-api.polymarket.com/events",
                         params={"slug": slug}, timeout=10)
        data = r.json()
        events = data if isinstance(data, list) else data.get("events", [])
        if events:
            print(f"FOUND: {slug} => {events[0].get('title', '?')[:60]}")
            break
    else:
        print(f"NOT FOUND: {fmt}")

# List available crypto events
print("\n--- Available crypto events ---")
r2 = requests.get("https://gamma-api.polymarket.com/events",
                   params={"limit": 10, "active": "true"}, timeout=10)
data2 = r2.json()
events2 = data2 if isinstance(data2, list) else data2.get("events", [])
for e in events2[:8]:
    title = e.get("title", "?")
    slug = e.get("slug", "?")
    if any(k in title.lower() for k in ["btc", "eth", "bitcoin", "ethereum", "up", "down"]):
        print(f"  {title[:70]} | slug: {slug[:50]}")
