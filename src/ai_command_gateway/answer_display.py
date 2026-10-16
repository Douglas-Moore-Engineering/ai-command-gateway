"""Plain-text presentation of evidence answers; no inference or execution."""
import json
import unicodedata


def _plain(value):
    # Prevent terminal escape/control sequences from source or question strings.
    return ''.join(c if not unicodedata.category(c).startswith('C') else ' ' for c in str(value))


def render_answer(report: dict) -> str:
    local = report.get('response', report)
    answer = report.get('answer')
    lines = [f"Question: {_plain(local['question'])}", '']
    if 'model' in report:
        model = report['model']
        lines.append(f"Model status: {model['status']} ({model['reason_code']}).")
    if answer and answer['origin'] == 'model':
        lines.append('Model explanation: citation bindings and numeric tokens checked; semantic accuracy requires review.')
        sentences = answer['sentences']
    else:
        lines.append('Answer from verified local observations (no model-written explanation).')
        sentences = [{'text': item['text'], 'citations': [item['citation']]}
                     for item in local['claims']]
    lines.append('')
    citations = []
    for sentence in sentences:
        markers = []
        for citation in sentence['citations']:
            if citation not in citations:
                citations.append(citation)
            markers.append(f'[{citations.index(citation) + 1}]')
        lines.append(f"{_plain(sentence['text'])} {' '.join(markers)}")
    if not sentences:
        lines.append(_plain(local['message']))
    if citations:
        lines.extend(['', 'Sources:'])
        for index, citation in enumerate(citations, 1):
            lines.append(f"[{index}] " + _plain(f"{citation['filename']} — {citation['locator']} "
                                                f"(source {citation['source_id']}; evidence {citation['evidence_id']})"))
    lines.extend(['', 'Research observations only. This answer does not authorize equipment actions.'])
    if report.get('request_preview') is not None:
        lines.extend(['', 'Request preview (not sent):',
                      json.dumps(report['request_preview'], indent=2, ensure_ascii=True)])
    return '\n'.join(lines) + '\n'


def emit_answer(report: dict, args):
    style = args.format or ('text' if args.explain else 'json')
    if style == 'text':
        text = render_answer(report)
    else:
        text = json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(text, end='')
