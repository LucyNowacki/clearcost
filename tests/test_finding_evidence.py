import unittest
from finding_evidence import evidence_for

class EvidenceTests(unittest.TestCase):
    def test_reason_is_saved_model_text(self):
        t={'field':'cancellation_charge','value':'Cancellation requires 24 hours notice.','quote':'Notice must be 24 hours.','page':1,'uncertainty':None}
        e=evidence_for({'classification':'cancelled_visit_rate_mismatch'}, {'terms':[t],'warnings':[]})
        self.assertEqual(e['terms'],[t])
        self.assertEqual(e['calculation_source'],'controlled_template_v1')
    def test_unknown_reason_is_reviewable(self):
        t={'field':'minimum_charge','value':'GBP 100 minimum','quote':'Minimum GBP 100','page':1,'uncertainty':None}
        e=evidence_for({'classification':'new_rule'}, {'terms':[t],'warnings':['Check scope']})
        self.assertTrue(e['needs_further_review'])
        self.assertEqual(e['additional_terms'],[t])
    def test_missing_evidence_is_not_complete(self):
        e=evidence_for({'classification':'duplicate_job'}, {'terms':[]})
        self.assertTrue(e['needs_further_review'])
    def test_multiple_issues_preserve_rules(self):
        terms=[{'field':f,'value':'rule','uncertainty':None} for f in ['duplicate_policy','cancellation_charge']]
        e=evidence_for({'classification':'duplicate_job','issues':['duplicate_job','cancelled_visit_rate_mismatch']},{'terms':terms})
        self.assertEqual(len(e['terms']),2)
