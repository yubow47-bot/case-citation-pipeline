"""Build decisions/non_case_sources.csv (PROBLEMS #138).

Rows name printed reporter-slot abbreviations that cite periodicals, treaty
series or statutes rather than judgments. Three source kinds:
  * official lists retrieved 2026-10-16 (Department of Justice Canada list of
    abbreviations, UN Treaty Collection, GovInfo, legislation.gov.uk);
  * suffix conventions taken from the same DOJ list (`AltaL.Rev.` = Alberta Law
    Review, `Can.Bar Rev.` = Canadian Bar Review);
  * the corpus print-evidence channel audit/findings/non_case_sources_20261016/
    quote_channel.csv: >= 10 counted mentions, >= 3 citing decisions and >= 85% of
    mentions printed right after a quoted title. Case reports score ~0 there.
Abbreviations registered in reporter_jurisdiction.csv are never listed.

    python decisions/tools/build_non_case_sources.py
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANNEL = ROOT / 'audit/findings/non_case_sources_20261016/quote_channel.csv'
OUT = ROOT / 'decisions/non_case_sources.csv'
REVIEWER = 'Claude Opus 5.5 agent review (user-authorized; not human review)'
DATE = '2026-10-16'
DOJ = 'Department of Justice Canada List of Abbreviations (archived)'
DOJ_URL = ('https://www.justice.gc.ca/eng/rp-pr/csj-sjc/harmonization/denau/abbrevia.html '
           'retrieved 2026-10-16')
FIELDS = ['printed_form', 'normalized_key', 'match_type', 'material_type', 'verification_status',
          'source', 'source_locator', 'notes', 'reviewer', 'reviewed_at']
DOJ_JOURNALS = [
    ('Alta. L. Rev.', 'AltaL.Rev. Alberta Law Review'),
    ('Can. Bar Rev.', 'Can.Bar Rev. Canadian Bar Review'),
    ('C. de D.', 'C.deD. Les Cahiers de droit'),
    ('Dalhousie L.J.', 'DalhousieL.J. Dalhousie Law Journal'),
    ('Man. L.J.', 'Man.L.J. Manitoba Law Journal'),
    ('McGill L.J.', 'McGillL.J. McGill Law Journal'),
    ('Osgoode Hall L.J.', 'Osgoode HallL.J. Osgoode Hall Law Journal'),
    ("Queen's L.J.", "Queen's L.J. Queen's Law Journal"),
    ('R. du B. can.', 'R.du B.can. Revue du Barreau canadien'),
    ('R. du N.', 'R.du N. Revue du notariat'),
    ('R.G.D.', 'R.G.D. Revue generale de droit'),
    ('R.J.T.', 'R.J.T. Revue juridique Themis'),
    ('S.C.L.R.', 'S.C.L.R. Supreme Court Law Review'),
    ('Stat. L. Rev.', 'Stat.L.Rev. Statute Law Review'),
    ('U. of T. L.J.', 'U.of T.L.J. University of Toronto Law Journal'),
    ("Brook. J. Int'l L.", "Brook.J. Int'lL. Brooklyn Journal of International Law"),
    ('Can. J. Admin. L. & Prac.', 'Can.J.Admin. L.&Prac. Canadian Journal of Administrative Law & Practice'),
    ('R.C.L.F.', 'R.C.L.F. Revue de la common law en francais'),
    ('R.P.F.S.', 'R.P.F.S. Revue de planification fiscale et successorale'),
]
DOJ_STATUTES = [('R.S.C.', 'Revised Statutes of Canada'), ('R.S.O.', 'Revised Statutes of Ontario'),
                ('R.S.Q.', 'Revised Statutes of Quebec'), ('S.Q.', 'Statutes of Quebec')]
SUFFIXES = [('L. Rev.', 'Law Review'), ('Law Rev.', 'Law Review'), ('Law Review', 'Law Review'),
            ('Bar Rev.', 'Bar Review'), ('Bar. Rev.', 'Bar Review')]


def nk(s):
    return re.sub(r'[^A-Za-z0-9]', '', s or '').lower()


def official():
    for form, entry in DOJ_JOURNALS:
        yield (form, 'exact', 'periodical', 'verified_official_source', DOJ,
               "%s: Law Journals and Law Reports entry '%s'" % (DOJ_URL, entry), '')
    for form, entry in DOJ_STATUTES:
        yield (form, 'exact', 'statute', 'verified_official_source', DOJ,
               "%s: List of Abbreviations entry '%s %s'" % (DOJ_URL, form, entry), '')
    for form, name in SUFFIXES:
        yield (form, 'suffix', 'periodical', 'verified_official_source', DOJ,
               "%s: entries 'AltaL.Rev. Alberta Law Review', 'Stat.L.Rev. Statute Law Review', "
               "'Can.Bar Rev. Canadian Bar Review'" % DOJ_URL,
               "A reporter-slot abbreviation ending in '%s' names a %s; the suffix must follow "
               "a space or period and something must precede it." % (form, name))
    un = 'United Nations Treaty Collection'
    yield ('U.N.T.S.', 'exact', 'treaty_series', 'verified_official_source', un,
           'https://treaties.un.org/Pages/Content.aspx?path=DB/UNTS/pageIntro_en.xml retrieved '
           "2026-10-16: 'The United Nations Treaty Series (UNTS) is a publication produced by the ...'", '')
    yield ('L.N.T.S.', 'exact', 'treaty_series', 'verified_official_source', un,
           'https://treaties.un.org/pages/LONOnline.aspx?clang=_en retrieved 2026-10-16: '
           "'League of Nations Treaty Series'", '')
    yield ('Stat.', 'exact', 'statute', 'verified_official_source',
           'GovInfo (U.S. Government Publishing Office) - United States Statutes at Large',
           'https://www.govinfo.gov/help/statute retrieved 2026-10-16: Statutes at Large citation '
           "example 'citation:\"119 Stat. 3822\"'", '')
    leg = ('legislation.gov.uk (The National Archives); '
           'Department of Justice Canada List of Abbreviations (archived)')
    yield ('Geo.', 'exact', 'statute', 'verified_official_source', leg,
           'https://www.legislation.gov.uk/ukpga/Geo5/1-2/46/contents retrieved 2026-10-16: '
           "'Copyright Act 1911 ... 1911 c. 46 (Regnal. 1_and_2_Geo_5)'; %s: 'Geo. George'" % DOJ_URL,
           'Regnal-year statute citation (`10 Geo. 5, c. 1`): a monarch abbreviation in the reporter slot.')
    yield ('Vict.', 'exact', 'statute', 'verified_official_source', leg,
           'https://www.legislation.gov.uk/ukpga/Vict/30-31/3/contents retrieved 2026-10-16: '
           "'British North America Act 1867 ... 1867 c. 3 (Regnal. 30_and_31_Vict)'; "
           "%s: 'Vict. Victoria'" % DOJ_URL,
           'Regnal-year statute citation (`30 & 31 Vict., c. 3`).')
    yield ('J. Soc. Welfare & Fam. L.', 'exact', 'periodical', 'verified_official_source',
           'University of British Columbia, Peter A. Allard School of Law (author research record); '
           'Taylor & Francis Online (publisher article metadata)',
           'https://researchers.allard.ubc.ca/en/publications/'
           'penalizing-womens-fear-intimate-partner-violence-and-parental-ali/ '
           'retrieved 2026-10-16: Sheehy and Boyd (2020), Journal of Social Welfare and Family Law, '
           '42(1), 80-91, DOI 10.1080/09649069.2020.1701940; '
           'https://www.tandfonline.com/doi/abs/10.1080/09649069.2020.1701940 '
           'publisher search metadata confirms journal, volume 42 issue 1, pages 80-91 '
           '(direct fetch returned 403); '
           'corpus SCC_2026scc16 prints the abbreviated journal name with the same article, '
           'year, volume and first page',
           'Exact journal abbreviation supported by matching author/title/year/volume/page '
           'metadata, independently of the corpus quoted-title frequency threshold. '
           'Follow-up reviewed by Codex agent (not human review), 2026-10-16.',
           'Codex agent review (user-authorized; not human review)')


def channel(registered):
    with CHANNEL.open(encoding='utf-8') as f:
        for r in csv.DictReader(f):
            n, q, d = int(r['mentions']), int(r['quoted_title_mentions']), int(r['citing_decisions'])
            if r['normalized_key'] in registered or n < 10 or d < 3 or q < 0.85 * n:
                continue
            yield (r['printed_form'], 'exact', 'periodical', 'verified_print_evidence',
                   'Corpus print evidence: quoted article title immediately before the citation',
                   'audit/findings/non_case_sources_20261016/quote_channel.csv normalized_key=%s: '
                   '%d of %d counted mentions (%s) in %d citing decisions'
                   % (r['normalized_key'], q, n, r['quoted_share'], d),
                   'Case reports score ~0 in the same channel (S.C.R. 0.001, O.R. 0.000, L.J.K.B. 0.000).')


def main():
    with (ROOT / 'decisions/reporter_jurisdiction.csv').open(encoding='utf-8-sig') as f:
        reporters = list(csv.DictReader(f))
    registered = {r['normalized_key'] for r in reporters} | {nk(r['abbreviation']) for r in reporters}
    rows, seen = [], set()
    for entry in list(official()) + list(channel(registered)):
        form, match, material, status, source, locator, notes = entry[:7]
        reviewer = entry[7] if len(entry) > 7 else REVIEWER
        key = nk(form)
        marker = key if match == 'exact' else 'suffix:' + form
        if marker in seen or (match == 'exact' and key in registered):
            continue
        seen.add(marker)
        rows.append(dict(zip(FIELDS, (form, key, match, material, status, source, locator, notes,
                                      reviewer, DATE))))
    with OUT.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    print(len(rows), 'rows ->', OUT)


if __name__ == '__main__':
    main()
