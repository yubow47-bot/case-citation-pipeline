"""Original-offset quotation boundary fixtures for the experimental context layer."""
import unittest

try:
    from .scopes import quotation_scopes, quote_scope_at, quote_scope_for_span
except ImportError:
    from scopes import quotation_scopes, quote_scope_at, quote_scope_for_span


class QuotationScopeTests(unittest.TestCase):
    def test_nested_scopes_and_unicode_offsets_are_stable(self):
        text = 'É😀 “The Court said «Smith, supra» yesterday.”'
        scopes = quotation_scopes(text)
        outer, inner = scopes
        self.assertEqual(text[outer['start']:outer['end']], '“The Court said «Smith, supra» yesterday.”')
        self.assertEqual(text[inner['content_start']:inner['content_end']], 'Smith, supra')
        self.assertEqual(inner['parent_scope_id'], outer['scope_id'])
        self.assertEqual(inner['depth'], 1)
        self.assertEqual(quote_scope_at(text.index('Smith'), scopes), inner)
        self.assertEqual(quote_scope_for_span(text.index('Smith'), text.index(' yesterday'), scopes), None)
        self.assertEqual(scopes, quotation_scopes(text))

    def test_unclosed_quote_is_uncertain_and_cannot_reach_next_paragraph(self):
        text = 'The appellant " sun in his eyes - was rejected.\n[22] In Hundal, supra.'
        scopes = quotation_scopes(text)
        self.assertFalse(scopes[0]['closed'])
        self.assertTrue(scopes[0]['uncertain'])
        self.assertEqual(scopes[0]['end'], text.index('\n'))
        self.assertIsNone(quote_scope_at(text.index('Hundal'), scopes))

    def test_mixed_quotes_end_locally_and_retain_uncertainty(self):
        text = 'a "Monday morning quarterback” approach. Smith, supra.\n“effective[ly] repeal[ed] s. 11.1". Jones, supra.'
        scopes = quotation_scopes(text)
        self.assertEqual(len(scopes), 2)
        self.assertTrue(all(s['closed'] and s['uncertain'] for s in scopes))
        self.assertTrue(all(s['boundary_reason'] == 'mixed_double_quote_pair' for s in scopes))
        self.assertIsNone(quote_scope_at(text.index('Smith'), scopes))
        self.assertIsNone(quote_scope_at(text.index('Jones'), scopes))

    def test_nested_straight_quotes_are_not_misread_as_mixed_closers(self):
        text = '“The witness said "Smith" in evidence.”'
        scopes = quotation_scopes(text)
        self.assertEqual(len(scopes), 2)
        self.assertTrue(all(s['closed'] and not s['uncertain'] for s in scopes))
        self.assertEqual(quote_scope_at(text.index('Smith'), scopes)['depth'], 1)

    def test_orphan_closer_and_uncertain_ancestor_cannot_be_reliable_scopes(self):
        text = 'A missing opening mark ends here”.\n“An unclosed parent contains «Smith, supra»'
        scopes = quotation_scopes(text)
        self.assertEqual(quote_scope_at(text.index('missing'), scopes)['boundary_reason'], 'orphan_closing_delimiter')
        inner = quote_scope_at(text.index('Smith'), scopes)
        self.assertTrue(inner['closed'])
        self.assertTrue(inner['uncertain'])
        self.assertEqual(inner['boundary_reason'], 'uncertain_ancestor')


if __name__ == '__main__':
    unittest.main()
