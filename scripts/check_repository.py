"""Check repository links, candidate IDs and preserved source integrity; offline only."""
import csv
import hashlib
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
errors = []
links = 0
for file in root.rglob('*.md'):
    if '.git' in file.parts:
        continue
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', file.read_text()):
        if target.startswith(('https:', 'http:', 'mailto:', '#')):
            continue
        links += 1
        path = target.split('#', 1)[0]
        if not (file.parent / path).resolve().exists():
            errors.append(f'{file.relative_to(root)}: missing {target}')

def rows(path):
    with (root / path).open(newline='') as file:
        return list(csv.DictReader(file))

requirements = rows('requirements/requirements.csv')
acceptance = rows('requirements/acceptance.csv')
req_ids = {row['id'] for row in requirements}
ac_ids = {row['id'] for row in acceptance}
if req_ids != {f'REQ-{i:02}' for i in range(1, 7)} or len(requirements) != 6:
    errors.append('Requirement IDs differ from DISC-001')
if ac_ids != {f'AC-{i:02}' for i in range(1, 7)} or len(acceptance) != 6:
    errors.append('Acceptance IDs differ from DISC-001')
trace = rows('requirements/traceability.csv')
for row in trace:
    if row['requirement'] not in req_ids or row['acceptance'] not in ac_ids:
        errors.append(f'Unresolved trace: {row}')
    for measurement in row['measurement'].split('; '):
        if not (root / 'governance/measurements' / f'{measurement}.md').exists():
            errors.append(f'Missing measurement {measurement}')
if {row['requirement'] for row in trace} != req_ids:
    errors.append('Incomplete requirement trace coverage')
open_items = rows('customer/open-items.csv')
if {row['id'] for row in open_items} != {f'OPEN-{i:02}' for i in range(1, 9)} or len(open_items) != 8:
    errors.append('Open-item IDs differ from DISC-001')
manifest = json.loads((root / 'customer/source-manifest.json').read_text())
source = root / 'customer' / manifest['file']
if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['sha256']:
    errors.append('Discovery source SHA-256 mismatch')
for file in root.rglob('*'):
    if '.git' in file.parts or not file.is_file():
        continue
    if file.name == 'SKILL.md':
        errors.append(f'Internal instruction file: {file.relative_to(root)}')
    if file.suffix == '.md' and 'skill://' in file.read_text():
        errors.append(f'Internal package locator: {file.relative_to(root)}')
if errors:
    print('\n'.join(errors))
    raise SystemExit(1)
print(f'PASS: {links} local file links; 6 requirements; 6 criteria; 8 open items; trace IDs; original SHA-256; no internal instruction files.')
print('Scope: repository consistency only; application, remote CI, rendering and acceptance not evaluated.')
