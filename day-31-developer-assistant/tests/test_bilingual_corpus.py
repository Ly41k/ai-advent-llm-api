"""Real explicit corpus/FTS/provenance; no model calls or semantic acceptance."""
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from bublik_developer.errors import DeveloperError, ErrorCode
from bublik_developer.rag.corpus import ProjectCorpus
from bublik_developer.rag.index import ProjectIndex, build_index
from bublik_developer.rag.state import ProjectState
from bublik_developer.workspace import ProjectWorkspace

APP=Path(__file__).resolve().parents[1]


class BilingualCorpusTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name).resolve();self.root=self.parent/'repo';self.root.mkdir()
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        (self.root/'README.md').write_text('# Fixture\nExplicit project docs only.\n')
        self.docs=self.root/'day-31-developer-assistant/project/docs';self.docs.mkdir(parents=True)
        for name in ('architecture','memory','tooling','api'):
            for suffix in ('.md','.ru.md'):
                shutil.copy2(APP/'project/docs'/(name+suffix),self.docs/(name+suffix))
        self.workspace=ProjectWorkspace.open(self.root,'bilingual-fixture')
        self.corpus=ProjectCorpus(self.workspace);self.state=ProjectState(self.workspace,self.parent/'state')

    def test_explicit_eight_docs_ignore_unlisted_translation(self):
        (self.docs/'private.ru.md').write_text('# Not allowlisted\nDO_NOT_INDEX_78345\n')
        docs=self.corpus.collect().documents
        self.assertEqual(len(docs),9)
        self.assertEqual(sum(d.source.endswith('.ru.md') for d in docs),4)
        self.assertFalse(any('DO_NOT_INDEX_78345' in d.text for d in docs))

    def test_russian_source_spans_and_freshness(self):
        build_index(self.corpus,self.state)
        with ProjectIndex.current(self.state,self.corpus) as index:
            self.assertEqual(index.verify()['status'],'verified')
            source='day-31-developer-assistant/project/docs/architecture.ru.md'
            path=self.docs/'architecture.ru.md';text=path.read_text()
            rows=list(index.db.execute('SELECT chunk_id FROM chunks WHERE source=?',(source,)))
            self.assertTrue(rows)
            for row in rows:
                hit=index.evidence(row['chunk_id'])
                self.assertEqual(hit['quote'],text[hit['start']:hit['end']])
                self.assertEqual(hit['raw_digest'],sha256(path.read_bytes()).hexdigest())
            path.write_text(text+'\nNew documented change.\n')
            with self.assertRaises(DeveloperError) as error:index.fresh()
            self.assertEqual(error.exception.code,ErrorCode.INDEX_STALE)

    def test_russian_allowlisted_symlink_rejected(self):
        path=self.docs/'tooling.ru.md';path.unlink()
        outside=self.parent/'outside.md';outside.write_text('# Outside\nnot a corpus source\n')
        path.symlink_to(outside)
        with self.assertRaises(DeveloperError) as error:self.corpus.collect()
        self.assertEqual(error.exception.code,ErrorCode.PERMISSION_DENIED)
