import importlib.util
import json
from pathlib import Path
import sqlite3
import unittest

spec = importlib.util.spec_from_file_location('fix1_zone_views', Path(__file__).resolve().parents[1] / 'fix1_zone_views.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ZoneViewTests(unittest.TestCase):
    def test_view_masks_preserve_zero_sources_and_unknown_zones(self):
        db = sqlite3.connect(':memory:')
        db.executescript('CREATE TABLE docs(sid TEXT,court TEXT,eligible INTEGER); CREATE TABLE edges(sid TEXT,gid TEXT,mentions INTEGER,history INTEGER,payload TEXT);')
        db.executemany('INSERT INTO docs VALUES(?,?,?)', [('a','SCC',1),('zero','SCC',1),('excluded','SCC',0),('other','ONCA',1)])
        for gid, zone, history, mentions in [('history','headnote_only',1,2),('headnote','headnote_only',0,1),('body','reasons_only',0,3),('unknown','unknown',0,1)]:
            payload = json.dumps({'zone_profile':zone,'own_case_history':bool(history)})
            db.execute('INSERT INTO edges VALUES(?,?,?,?,?)', ('a',gid,mentions,history,payload))
        result = module.summarize_scc(db)['views']
        self.assertEqual([(result[v]['N'],result[v]['E'],result[v]['K'],result[v]['O']) for v in result], [(2,4,4,7),(2,3,3,5),(2,2,2,4)])
        self.assertEqual(result['without_headnote_only']['median_links_including_zero'],1)
        self.assertEqual(result['without_headnote_only']['zone_profile_edge_counts']['unknown'],1)
        db.execute("UPDATE edges SET payload='{}'")
        self.assertEqual(module.summarize_scc(db)['status'],'UNAVAILABLE_IN_EDGE_SCHEMA')
        db.close()


if __name__ == '__main__':
    unittest.main()
