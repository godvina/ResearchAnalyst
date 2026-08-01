"""Insert compelling 'Did You Know' trawler alerts for the demo."""
import urllib.request, json, uuid

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'

alerts = [
    {
        'alert_type': 'network_anomaly',
        'severity': 'high',
        'title': 'Marcus Blackwell and Catherine Sterling traveled to the same 6 international cities within overlapping timeframes — Paris, Morocco, Dubai, Moscow, Barcelona, and Tokyo. This coordinated pattern across 4 continents suggests jointly planned travel, not coincidence.',
        'summary': 'Cross-referencing travel entities reveals a systematic international circuit. In trafficking cases, coordinated multi-country travel by a principal and key associate indicates operational expansion, venue scouting, or victim transportation across borders.',
        'entity_names': json.dumps(['Marcus Blackwell', 'Catherine Sterling', 'Paris', 'Dubai', 'Morocco']),
    },
    {
        'alert_type': 'financial_pattern',
        'severity': 'high',
        'title': 'Trimark Industries appears in 17 relationship connections across 5 separate financial control incidents — more than any other organization in this case. It functions as the primary financial vehicle for the enterprise.',
        'summary': 'Trimark Industries connects to Marcus Blackwell through structured accounts, payment trails, and controlled financial instruments. This level of organizational involvement typically indicates a shell entity used to obscure beneficial ownership and launder proceeds.',
        'entity_names': json.dumps(['Trimark Industries', 'Marcus Blackwell']),
    },
    {
        'alert_type': 'convergence_alert',
        'severity': 'high',
        'title': '4 subjects — Catherine Sterling, Daniel Whitmore, Jonathan Mercer, and Victor Nash — all traveled to Paris independently. Paris is the only non-US location where this many subjects converge. What happened there?',
        'summary': 'Convergence of 4+ subjects at a single international location is a strong indicator of a planned meeting or coordinated operation. Subpoena hotel records, flight manifests, and financial transactions for all 4 subjects during overlapping date ranges in Paris.',
        'entity_names': json.dumps(['Catherine Sterling', 'Daniel Whitmore', 'Paris', 'Victor Nash']),
    },
    {
        'alert_type': 'network_anomaly',
        'severity': 'medium',
        'title': 'Victor Nash appears at every international destination where Marcus Blackwell traveled — Paris, Barcelona, Tokyo, Dubai, Morocco, and Moscow. This shadow pattern suggests Nash served as an advance coordinator or logistics facilitator for the network.',
        'summary': 'When one associate mirrors the travel pattern of a principal subject across 6+ countries, it indicates either a facilitator role (preparing venues, managing logistics) or a financial role (moving money ahead of operations). Victor Nash warrants priority investigation.',
        'entity_names': json.dumps(['Victor Nash', 'Marcus Blackwell', 'Dubai', 'Tokyo', 'Barcelona']),
    },
    {
        'alert_type': 'temporal_anomaly',
        'severity': 'medium',
        'title': 'Daniel Whitmore is the only subject with connections to both Paris and Antalya (Turkey). His travel pattern deviates from the core NY-Palm Beach circuit — suggesting a separate operational role in Mediterranean and Middle Eastern locations.',
        'summary': 'Whitmore\'s geographic footprint extends into Turkey and the Eastern Mediterranean while other subjects stay in Western Europe. This may indicate responsibility for a specific regional operation or pipeline that the other subjects don\'t directly manage.',
        'entity_names': json.dumps(['Daniel Whitmore', 'Antalya', 'Paris', 'Barcelona']),
    },
]

for alert in alerts:
    alert_id = str(uuid.uuid4())
    sql = (
        f"INSERT INTO trawler_alerts (alert_id, case_id, scan_id, alert_type, severity, title, summary, entity_names) "
        f"VALUES ('{alert_id}'::uuid, '{CASE_ID}'::uuid, '{alert_id}'::uuid, "
        f"'{alert['alert_type']}', '{alert['severity']}', "
        f"$${alert['title']}$$, "
        f"$${alert['summary']}$$, "
        f"'{alert['entity_names']}'::jsonb)"
    )
    body = json.dumps({'sql': sql}).encode()
    req = urllib.request.Request(API + '/admin/run-migration', data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())
        print(f"  Inserted: {alert['title'][:60]}... ({result.get('rowcount', '?')})")
    except Exception as e:
        print(f"  Error: {e}")
        if hasattr(e, 'read'):
            print(f"    {e.read().decode()[:200]}")

print("\nDone. Refresh to see new Did You Know cards.")
