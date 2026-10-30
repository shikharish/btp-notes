#!/usr/bin/env python3
"""Final Luna classifier: check setup, then run a bounded, resumable two-pass job."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import sqlite3
import sys
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

try:
    from . import evidence, pi_runner
except ImportError:  # Also support: python classifier/classify.py ...
    import evidence
    import pi_runner

HERE = Path(__file__).resolve().parent
FIELDS = ('record_id', 'url', 'project', 'title', 'body')


def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False)


def grade(row):
    """Frozen recipe-and-outcomes-v1 mapping. Pending is NOT level 4."""
    if row['target'] != 'single' or row['external'] != 'no' or any(row[k] is None for k in ('recipe', 'observed', 'expected')):
        return 'pending'
    r, o, e = row['recipe'], row['observed'], row['expected']
    if r == 0 or (o == 0 and e == 0):
        return 3
    return 1 if r == 2 and o == e == 1 else 2


def normalize(raw):
    """Normalize schema, not prose. Preserve conflicting text versions separately."""
    def field(*names):
        values = [raw[n] for n in names if raw.get(n) is not None]
        if any(not isinstance(v, str) for v in values):
            raise ValueError('Expected text/null for ' + '/'.join(names))
        if len(set(values)) > 1:
            raise ValueError('Conflicting input schema aliases: ' + '/'.join(names))
        return values[0] if values else ''
    if not isinstance(raw, dict):
        raise ValueError('Each input row must be an object')
    url = field('url')
    if not url:
        raise ValueError('Each report needs its original URL')
    project = field('project')
    if not project:
        parsed = urlsplit(url)
        parts = parsed.path.strip('/').split('/')
        if parsed.hostname == 'api.github.com' and parts[:1] == ['repos']:
            project = '/'.join(parts[1:3])
        elif parsed.hostname in ('github.com', 'www.github.com'):
            project = '/'.join(parts[:2])
    source = {'url': url, 'project': project, 'title': field('title', 'issue_title'), 'body': field('body', 'issue_body')}
    identity = 'r_' + hashlib.sha256(encoded(source).encode()).hexdigest()
    source_id = next((raw[k] for k in ('source_id', 'bug_id', 'record_id', 'id') if raw.get(k) is not None), None)
    return dict(record_id=identity, **source, source_id=source_id)


def input_files(path):
    path = Path(path).resolve()
    if path.is_dir():
        files = sorted(path.glob('*_data_part*.parquet'))
        if not files and (path / 'catalog.parquet').is_file():
            files = [path / 'catalog.parquet']
            if (path / 'conflicting-reports.parquet').is_file():
                files.append(path / 'conflicting-reports.parquet')
        if not files:
            files = sorted(path.glob('*.parquet'))
    else:
        files = [path] if path.is_file() else []
    if not files or any(p.suffix not in ('.parquet', '.jsonl') for p in files):
        raise ValueError('Input must be JSONL, Parquet, or a directory of Parquet reports')
    return files


def read_input(files):
    """Stream rows; DuckDB is optional and required only for Parquet."""
    if files[0].suffix == '.jsonl':
        for path in files:
            with path.open(encoding='utf-8') as stream:
                for number, line in enumerate(stream, 1):
                    if line.strip():
                        try:
                            yield normalize(pi_runner._loads(line))
                        except (ValueError, TypeError) as exc:
                            raise ValueError(f'{path}:{number}: {exc}') from exc
        return
    try:
        duckdb = importlib.import_module('duckdb')
    except ImportError as exc:
        raise RuntimeError('Parquet needs DuckDB: uv run --with duckdb==2.0.0 classifier/classify.py ...') from exc
    db = duckdb.connect()
    try:
        db.execute("SET memory_limit='2GB'")
        db.execute('SET threads=2')
        # Validate EACH file before union: never turn unrelated provenance rows into empty reports.
        for path in files:
            names = set(db.read_parquet(str(path)).columns)
            if not ('url' in names and names & {'title', 'issue_title'} and names & {'body', 'issue_body'}):
                raise ValueError('Not a report Parquet schema: ' + str(path))
        relation = db.read_parquet([str(p) for p in files], union_by_name=True)
        names = relation.columns
        keep = [k for k in ('url', 'project', 'title', 'issue_title', 'body', 'issue_body', 'source_id', 'bug_id', 'record_id', 'id') if k in names]
        relation.select(','.join('"' + k + '"' for k in keep)).create_view('normalized_reports')
        cursor = db.execute('SELECT * FROM normalized_reports')
        while values := cursor.fetchmany(1000):
            for row in values:
                yield normalize(dict(zip(keep, row, strict=True)))
    finally:
        db.close()


class Store:
    def __init__(self, root, files):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / 'state.sqlite'
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS config(value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reports(record_id TEXT PRIMARY KEY, source TEXT NOT NULL,
                    category TEXT, metrics TEXT, vagueness TEXT, error TEXT);
                CREATE TABLE IF NOT EXISTS identities(record_id TEXT, source_id TEXT,
                    PRIMARY KEY(record_id,source_id));''')
            code = [HERE / n for n in ('classify.py', 'pi_runner.py', 'evidence.py', 'prompts/bug.md', 'prompts/vagueness.md')]
            config = encoded({'pipeline': {p.relative_to(HERE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in code},
                              'input': [{'path': str(p), 'bytes': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns} for p in files],
                              'models': {'type': 'openai-codex/gpt-6-luna:high', 'grade': 'openai-codex/gpt-6-luna:max'}})
            prior = db.execute('SELECT value FROM config').fetchone()
            if prior and prior[0] != config:
                raise ValueError('Input or classifier changed. Use a new output directory; do not overwrite old results.')
            if not prior:
                db.execute('INSERT INTO config VALUES (?)', [config])

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=60)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def rows(self, batch):
        with self.connect() as db:
            return {r['record_id']: dict(db.execute('SELECT * FROM reports WHERE record_id=?', [r['record_id']]).fetchone()) for r in batch}

    def update(self, record_id, **values):
        if not values or set(values) - {'category', 'metrics', 'vagueness', 'error'}:
            raise ValueError('Invalid cache update')
        with self.connect() as db:
            db.execute('''UPDATE reports SET category=COALESCE(category,?),
                metrics=COALESCE(metrics,?), vagueness=COALESCE(vagueness,?), error=?
                WHERE record_id=?''', [values.get('category'), values.get('metrics'),
                                      values.get('vagueness'), values.get('error'), record_id])

    def select(self, files, limit, retry):
        with self.connect() as db:
            db.execute('CREATE TEMP TABLE chosen(record_id TEXT PRIMARY KEY)')
            count = 0
            for row in read_input(files):
                fresh = db.execute('INSERT OR IGNORE INTO chosen VALUES (?)', [row['record_id']]).rowcount != 0
                db.execute('INSERT OR IGNORE INTO reports(record_id,source) VALUES (?,?)', [row['record_id'], encoded(row)])
                db.execute('INSERT OR IGNORE INTO identities VALUES (?,?)', [row['record_id'], encoded(row['source_id'])])
                db.commit()  # Workers can persist results while input is streamed.
                if not fresh:
                    continue
                count += 1
                saved = db.execute('SELECT * FROM reports WHERE record_id=?', [row['record_id']]).fetchone()
                complete = saved['category'] is not None and (saved['category'] != 'bug' or saved['vagueness'] is not None)
                if not complete:
                    if saved['error'] and not retry:
                        raise RuntimeError(f"Earlier failure: inspect attempts/, then resume with --retry-failed. {row['record_id']}")
                    if saved['error']:
                        self.update(row['record_id'], error=None)
                    yield {k: row[k] for k in FIELDS}
                if limit is not None and count >= limit:
                    break

    def export(self):
        counts, errors = {}, 0
        with self.connect() as db, (self.root / 'labels.jsonl').open('w', encoding='utf-8') as labels, \
                (self.root / 'errors.jsonl').open('w', encoding='utf-8') as failed, \
                (self.root / 'records.csv').open('w', newline='', encoding='utf-8') as mapping:
            writer = csv.writer(mapping)
            writer.writerow(['record_id', 'source_id', 'url'])
            for row in db.execute('SELECT * FROM reports ORDER BY rowid'):
                source = pi_runner._loads(row['source'])
                for identity in db.execute('SELECT source_id FROM identities WHERE record_id=? ORDER BY source_id', [row['record_id']]):
                    writer.writerow([row['record_id'], pi_runner._loads(identity['source_id']), source['url']])
                complete = row['category'] is not None and (row['category'] != 'bug' or row['vagueness'] is not None)
                if complete:
                    value = None
                    if row['vagueness'] is not None:
                        try:
                            value = json.loads(row['vagueness'])
                        except (ValueError, TypeError) as exc:
                            raise RuntimeError(f"Corrupt cached label: {row['record_id']}") from exc
                    labels.write(encoded({'record_id': row['record_id'], 'category': row['category'], 'vagueness': value}) + '\n')
                    key = row['category'] + (':' + str(value) if row['category'] == 'bug' else '')
                    counts[key] = counts.get(key, 0) + 1
                else:
                    errors += 1
                    failed.write(encoded({'record_id': row['record_id'], 'error': row['error'] or 'unfinished'}) + '\n')
        summary = {'completed': sum(counts.values()), 'failed_or_unfinished': errors, 'categories': counts}
        (self.root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        return summary


def batches(rows, stage='type'):
    batch, size, images = [], 0, 0
    for row in rows:
        packet = pi_runner._packet(stage, [row])[0]
        length = len(encoded(packet)) + sum(Path(p).stat().st_size for p in row.get('files', []) if Path(p).suffix.lower() not in ('.png', '.jpg', '.jpeg', '.gif', '.webp'))
        pictures = sum(Path(p).suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif', '.webp') for p in row.get('files', []))
        if length > 200000:
            raise ValueError('Single report exceeds safe context budget (not truncated): ' + row['record_id'])
        if batch and (len(batch) >= 10 or size + length > 200000 or images + pictures > 12):
            yield batch
            batch, size, images = [], 0, 0
        batch.append(row)
        size += length
        images += pictures
    if batch:
        yield batch


def process(batch, store):
    def infer(stage, records):
        attempts = store.root / 'attempts'
        attempts.mkdir(exist_ok=True)
        return pi_runner.infer(stage, records, attempts / (stage + '-' + uuid.uuid4().hex))
    saved = store.rows(batch)
    new = [r for r in batch if saved[r['record_id']]['category'] is None]
    if new:
        for row in infer('type', new):
            store.update(row['record_id'], category=row['category'], error=None)
    saved = store.rows(batch)
    bugs = [r for r in batch if saved[r['record_id']]['category'] == 'bug' and saved[r['record_id']]['vagueness'] is None]
    enriched = [dict(r, **{k: v for k, v in evidence.collect(r, store.root / 'evidence').items() if k in ('evidence', 'files', 'optional_files')}) for r in bugs]
    for group in batches(enriched, 'grade'):
        for row in infer('grade', group):
            store.update(row['record_id'], metrics=encoded(row), vagueness=encoded(grade(row)), error=None)


def run(args):
    files = input_files(args.input)
    store = Store(args.out, files)
    print('Checking Luna/high and Luna/max availability (no classification yet)...', flush=True)
    pi_runner.check()
    pending, stop, error = {}, False, None
    source = iter(batches(store.select(files, args.limit, args.retry_failed)))
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            while pending or not stop:
                while len(pending) < args.workers and not stop:
                    try:
                        group = next(source)
                    except StopIteration:
                        stop = True
                        break
                    pending[pool.submit(process, group, store)] = group
                if not pending:
                    break
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    group = pending.pop(future)
                    try:
                        future.result()
                        print('Completed batch of', len(group), flush=True)
                    except Exception as exc:
                        stop, error = True, exc
                        for row in store.rows(group).values():
                            if row['category'] is None or (row['category'] == 'bug' and row['vagueness'] is None):
                                store.update(row['record_id'], error=str(exc))
                        print('Stopped scheduling new work:', str(exc), file=sys.stderr, flush=True)
    finally:
        print(json.dumps(store.export(), indent=2), flush=True)
    if error:
        raise RuntimeError('Some work failed; existing results are saved. Inspect logs before --retry-failed.') from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('check', help='Check own Pi login and exact models; no inference')
    task = commands.add_parser('run', help='Classify explicit input and preserve progress')
    task.add_argument('input', type=Path)
    task.add_argument('--out', type=Path, required=True)
    scope = task.add_mutually_exclusive_group(required=True)
    scope.add_argument('--limit', type=int, help='First N distinct normalized report texts, including cached ones')
    scope.add_argument('--all', action='store_true', help='Entire input; only with owner approval')
    task.add_argument('--workers', type=int, choices=range(1, 11), default=10)
    task.add_argument('--retry-failed', action='store_true', help='Explicitly retry failures only; retain every attempt')
    args = parser.parse_args(argv)
    try:
        if args.command == 'check':
            print(json.dumps(pi_runner.check(), indent=2))
        else:
            if args.limit is not None and args.limit < 1:
                raise ValueError('--limit must be positive')
            run(args)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
