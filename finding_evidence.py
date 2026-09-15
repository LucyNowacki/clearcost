"""Connect calculated findings to saved model terms without treating drafts as rules."""
FIELD_MAP = {
    'rate_mismatch': ['standard_rate', 'supplements_and_exceptions'],
    'cancelled_visit_rate_mismatch': ['cancellation_charge'],
    'non_chargeable_incomplete': ['incomplete_visit_charge'],
    'duplicate_job': ['duplicate_policy'],
    'unverified': ['completion_evidence', 'effective_period', 'supplements_and_exceptions'],
    'match': ['standard_rate', 'supplements_and_exceptions'],
}


def evidence_for(line, extraction):
    issues = line.get('issues') or [line['classification']]
    fields = set()
    unmapped = []
    for issue in issues:
        if issue in FIELD_MAP:
            fields.update(FIELD_MAP[issue])
        else:
            unmapped.append(issue)
    terms = extraction.get('terms', [])
    relevant = [t for t in terms if t.get('field') in fields]
    # Unknown clauses are exposed for human assessment, never silently executed.
    additional = [t for t in terms if t.get('field') not in fields]
    complete = bool(relevant) and all(t.get('value') is not None and not t.get('uncertainty') for t in relevant)
    return {'terms': relevant, 'additional_terms': additional,
            'warnings': extraction.get('warnings', []),
            'needs_further_review': bool(unmapped) or not complete,
            'unmapped_issues': unmapped,
            'calculation_source': 'controlled_template_v1'}
