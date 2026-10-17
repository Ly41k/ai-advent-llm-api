"""Bounded, disposable SQLite FTS5/BM25 index. Day 30 files are read-only."""
import hashlib
import json
import re
import sqlite3
from common import ROOT, BASE_SHA, require

STOP = {'почему', 'работает', 'не', 'как', 'the', 'is', 'why', 'what', 'does', 'not', 'через', 'нужен'}
ALLOW = {'day-30-private-ai-service/README.md', 'day-30-private-ai-service/API.md'}


def corpus(root=ROOT.parent):
    rows = json.loads((ROOT / 'faq/bublik.json').read_text(encoding='utf-8'))
    docs = []
    for row in rows:
        require(row['origin_path'] in ALLOW, 'invalid_corpus', 500)
        raw = (root / row['origin_path']).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == row['file_sha256'], 'documentation_changed', 503)
        require(row['quote'] in raw.decode('utf-8'), 'invalid_corpus', 500)
        url = f"https://github.com/Ly41k/ai-advent-llm-api/blob/{BASE_SHA}/{row['origin_path']}#{row['anchor']}"
        common = {'topic': row['topic'], 'origin_url': url, 'origin_path': row['origin_path'], 'file_sha256': row['file_sha256']}
        docs.append({'id': row['id'], 'kind': 'faq', 'title': row['title'], 'text': row['text'], **common})
        docs.append({'id': row['id'].replace('FAQ-', 'DOC-'), 'kind': 'documentation', 'title': row['title'], 'text': row['quote'], **common})
    return docs


def retrieve(question, ticket=None, root=ROOT.parent):
    # Search the actual question plus bounded ticket observations. No user ID lookup.
    query_text = question
    if ticket:
        query_text += ' ' + ticket['description'] + ' ' + ticket['observed_error']
    def tokenize(text):
        return list(dict.fromkeys(w.casefold() for w in re.findall(r'[A-Za-zА-Яа-яЁё0-9]{2,32}', text) if w.casefold() not in STOP))[:32]
    question_terms = tokenize(question)
    terms = tokenize(query_text)
    docs = corpus(root)
    db = sqlite3.connect(':memory:')
    try:
        db.execute("CREATE VIRTUAL TABLE search USING fts5(title,text, tokenize='unicode61')")
        db.executemany('INSERT INTO search(rowid,title,text) VALUES (?,?,?)', ((i+1,d['title'],d['text']) for i,d in enumerate(docs)))
        query = ' OR '.join('"'+term+'"' for term in terms)
        question_query = ' OR '.join('"'+term+'"' for term in question_terms)
        # Ticket keywords may improve ranking, but cannot turn an unrelated
        # question (e.g. billing) into a documented authentication diagnosis.
        rows = db.execute('SELECT rowid FROM search WHERE search MATCH ? AND rowid IN (SELECT rowid FROM search WHERE search MATCH ?) ORDER BY bm25(search),rowid LIMIT 3', (query,question_query)).fetchall() if query and question_query else []
        return [docs[row[0]-1] for row in rows], {'method':'sqlite_fts5_bm25', 'indexed_chunks':len(docs), 'terms':terms, 'selected_chunks':len(rows)}
    finally:
        db.close()
