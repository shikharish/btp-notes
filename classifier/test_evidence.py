"""Offline tests: all transport/subprocess boundaries are mocked."""
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

try:
    from . import evidence as ev
except ImportError:
    import evidence as ev


def fetched(data=b'hello', kind='text/plain', url='https://public.org/file'):
    return data, url, kind, [{'url': url, 'status': 200}]


def archive(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, value in entries:
            z.writestr(name, value)
    return output.getvalue()


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.real_fetch = ev._fetch
        self.network = patch.object(ev, '_fetch', side_effect=AssertionError('unexpected network'))
        self.fetch = self.network.start()
        self.git = patch.object(ev.subprocess, 'run', side_effect=AssertionError('unexpected subprocess'))
        self.process_run = self.git.start()
        self.pdf = patch.object(ev.subprocess, 'Popen', side_effect=AssertionError('unexpected subprocess'))
        self.popen = self.pdf.start()

    def tearDown(self):
        self.pdf.stop()
        self.git.stop()
        self.network.stop()
        self.temp.cleanup()

    def report(self, body, **kw):
        return dict(record_id='1', title='bug', body=body,
                    project='owner/main', url='https://github.com/owner/main/issues/1', **kw)

    def test_cache_snapshot_and_full_body(self):
        body = 'x' * 100000 + '\n[repro](https://public.org/example.txt)'
        report = self.report(body)
        self.fetch.side_effect = None
        self.fetch.return_value = fetched()
        result = ev.collect(report, self.root)
        again = ev.collect(report, self.root)
        self.assertEqual(result, again)
        self.assertEqual(self.fetch.call_count, 1)
        saved_report = Path(result['files'][0]).parent / 'report.json'
        self.assertEqual(json.loads(saved_report.read_text())['body'], body)
        self.assertEqual(result['evidence'][0]['sha256'], hashlib.sha256(b'hello').hexdigest())
        changed = dict(report, body=body + '!')
        self.assertNotEqual(ev.collect(changed, self.root)['fingerprint'], result['fingerprint'])
        Path(result['optional_files'][0]).unlink()
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            ev.collect(report, self.root)

    def test_aliases_share_successful_and_failed_transport(self):
        report = self.report('[example](https://public.org/file#a)\n[example](https://public.org/file#b)')
        self.fetch.side_effect = None
        self.fetch.return_value = fetched()
        result = ev.collect(report, self.root)
        self.assertEqual(self.fetch.call_count, 1)
        self.assertEqual(len(result['evidence']), 3)
        self.fetch.reset_mock()
        self.fetch.side_effect = OSError('unavailable')
        failed_report = dict(report, record_id='2')
        result = ev.collect(failed_report, self.root)
        self.assertEqual(self.fetch.call_count, 1)
        self.assertEqual([i['status'] for i in result['evidence'][:2]], ['failed', 'failed'])
        self.assertEqual(ev.collect(failed_report, self.root), result)
        self.assertEqual(self.fetch.call_count, 1)

    def test_html_image_and_plain_input_file_are_collected(self):
        self.fetch.side_effect = lambda url: (fetched(b'{}', 'application/json', url)
            if url.endswith('.json') else fetched(b'\x89PNG\r\n\x1a\nbytes', 'image/png', url))
        report = self.report('<img src="https://public.org/opaque-uuid">\nhttps://public.org/input.json')
        result = ev.collect(report, self.root)
        self.assertEqual(self.fetch.call_count, 2)
        self.assertTrue(any(Path(p).suffix == '.png' for p in result['files']))
        self.assertTrue(any(i['url'].endswith('input.json') and i['status'] == 'saved' for i in result['evidence']))

    def test_partial_cache_fails_explicitly(self):
        report = self.report('no links')
        fingerprint = hashlib.sha256(json.dumps(report, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        (self.root / ('evidence-' + fingerprint)).mkdir()
        with self.assertRaisesRegex(RuntimeError, 'interrupted'):
            ev.collect(report, self.root)
        self.fetch.assert_not_called()

    def test_selection_records_all_and_benign_failures(self):
        report = self.report('incidental https://registry.npmjs.org/example\n'
                             '[bad](https://public.org/missing)\n'
                             '[solution](https://github.com/o/r/commit/abc)\n'
                             '[private](http://127.0.0.1/no)')
        self.fetch.side_effect = OSError('HTTP 404')
        result = ev.collect(report, self.root)
        statuses = {i['url']: i['status'] for i in result['evidence']}
        self.assertEqual(statuses['https://registry.npmjs.org/example'], 'not_fetched')
        self.assertEqual(statuses['https://public.org/missing'], 'failed')
        self.assertEqual(statuses['http://127.0.0.1/no'], 'excluded')
        self.assertEqual(statuses['https://github.com/o/r/commit/abc'], 'excluded')
        self.assertEqual(len(statuses), 5)
        self.assertIn('never implies', result['limitations'])
        self.assertEqual(self.fetch.call_count, 1)

    def test_url_guards_and_dns_rebinding(self):
        bad = ['http://localhost/a', 'http://127.0.0.1/a', 'http://[::1]/a',
               'http://x.local/a', 'https://public.org:444/a', 'https://public.org:0/a', 'https://a:b@public.org/a',
               'file:///etc/passwd', 'https://public.org/a\\b', 'http://2130706433/a',
               'https://public.org/?token=private', 'http://001.002.003.004/a']
        for url in bad:
            with self.subTest(url=url), self.assertRaises((ev.Rejected, ValueError)):
                ev._parts(url)
        for address in ['127.0.0.1', '10.0.0.1', '169.254.169.254', '192.0.2.1', '224.0.0.1', '::ffff:8.8.8.8']:
            answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443)),
                      (socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, 443))]
            with patch.object(ev.socket, 'getaddrinfo', return_value=answer):
                with self.subTest(address=address), self.assertRaises(ev.Rejected):
                    ev._resolve('public.org', 443, ev.time.monotonic() + 2)

    def test_chunks_exact_and_mandatory_budget(self):
        text = ('x\n' * 5500) + ('z' * 45000)
        chunks = list(ev._chunks(text))
        self.assertEqual(''.join(chunks), text)
        self.assertTrue(all(len(c) <= 8000 and len(c.splitlines()) <= 1000 for c in chunks))
        self.fetch.side_effect = None
        self.fetch.return_value = fetched(text.encode())
        result = ev.collect(self.report('\n'.join(f'[example](https://public.org/{i})' for i in range(8))), self.root)
        views = [Path(p).read_text() for p in result['files']]
        self.assertLessEqual(sum(map(len, views)), 40000)
        self.assertTrue(any('EXCERPT' in v for v in views))
        first = result['evidence'][0]['text_sources'][0]['parts']
        self.assertEqual(''.join(Path(p).read_text() for p in first), text)
        self.assertTrue(any('view_limited' in i for i in result['evidence']))

    def test_images_not_silently_dropped_and_resource_limit(self):
        self.fetch.side_effect = None
        self.fetch.return_value = fetched(b'\x89PNG\r\n\x1a\nbytes', 'image/png')
        body = '\n'.join(f'![picture](https://public.org/{i}.png)' for i in range(23))
        result = ev.collect(self.report(body), self.root)
        self.assertEqual(len(result['files']), 20)
        self.assertEqual(sum(i['status'] == 'limited' for i in result['evidence']), 3)
        self.assertTrue(all(Path(p).suffix == '.png' for p in result['files']))
        self.assertEqual(len(result['evidence']), 24)

    def test_zip_guards_and_exact_sources(self):
        values = [('demo/README.md', '# repro\r\n'), ('demo/main.py', 'print(1)\n')]
        self.assertEqual(ev._zip_text(archive(values)), values)
        for entries in [[('../escape', 'x')], [('/absolute', 'x')], [('x\\y', 'x')], [('C:/escape', 'x')],
                        [(f'a/{i}', 'x') for i in range(101)], [('large', 'x' * (200 * 1024 + 1))]]:
            with self.assertRaises(ev.Rejected):
                ev._zip_text(archive(entries))
        link = zipfile.ZipInfo('link'); link.external_attr = 0o120777 << 16
        with self.assertRaises(ev.Rejected):
            ev._zip_text(archive([(link, '../elsewhere')]))
        self.fetch.side_effect = None
        self.fetch.return_value = fetched(archive(values), 'application/zip')
        result = ev.collect(self.report('[example](https://public.org/example.zip)'), self.root)
        sources = result['evidence'][0]['text_sources']
        self.assertEqual([s['name'] for s in sources], [n for n, _ in values])
        for source, (_, expected) in zip(sources, values):
            self.assertEqual(''.join(Path(p).read_bytes().decode() for p in source['parts']), expected)

    def test_repo_pinned_git_and_main_repo_exclusion(self):
        commit = 'a' * 40
        self.process_run.side_effect = [subprocess.CompletedProcess([], 0, b'git version 2.43.0\n', b''),
                                subprocess.CompletedProcess([], 0, f'{commit}\tHEAD\n'.encode(), b'')]
        self.fetch.side_effect = None
        self.fetch.return_value = fetched(archive([('demo/README.md', 'example'), ('demo/main.js', 'throw 1;')]), 'application/zip')
        with patch.object(ev, '_resolve', return_value=['8.8.8.8']):
            result = ev.collect(self.report('[repro](https://github.com/alice/minimal-demo)\n[repro](https://github.com/owner/main)'), self.root)
        first = result['evidence'][0]
        self.assertEqual(first['commit'], commit)
        self.assertEqual(result['evidence'][1]['status'], 'excluded')
        self.fetch.assert_called_once_with(f'https://codeload.github.com/alice/minimal-demo/zip/{commit}')
        args, kwargs = self.process_run.call_args
        self.assertIn('http.curloptResolve=github.com:443:8.8.8.8', args[0])
        self.assertIn('credential.helper=', args[0])
        self.assertEqual(kwargs['env']['GIT_CONFIG_NOSYSTEM'], '1')
        self.assertNotIn('HTTPS_PROXY', kwargs['env'])
        self.assertIn('not historical', first['limitations'])

    def test_repo_names_are_ascii_and_not_dot_segments(self):
        for owner, name in [('alice', '.'), ('alice', '..'), ('.', 'demo'), ('..', 'demo'),
                            ('alice', '..git'), ('alice', '...git'), ('alice', 'démø'),
                            ('álîce', 'demo'), ('alice', '%2e%2e')]:
            with self.subTest(owner=owner, name=name), self.assertRaisesRegex(ev.Rejected, 'invalid repository'):
                ev._repo(f'https://github.com/{owner}/{name}', {})
        self.assertEqual(ev._repo('https://github.com/Alice-1/demo_2.0.git', {}), ('Alice-1', 'demo_2.0'))
        self.process_run.assert_not_called()
        self.fetch.assert_not_called()

    def test_html_pdf_and_rewrites(self):
        text = ev._text(b'<html><h1>Bug</h1><script>secret()</script><p>A &amp; B</p></html>', 'text/html', self.root / 'x')
        self.assertIn('A & B', text)
        self.assertNotIn('secret', text)
        with patch.object(ev.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(ev.Rejected, 'PDF unread'):
                ev._text(b'%PDF-1', 'application/pdf', self.root / 'x')
        process = Mock(stdout=io.BytesIO(b'PDF text'))
        process.wait.return_value = 0
        process.poll.return_value = 0
        self.popen.side_effect = None
        self.popen.return_value = process
        with patch.object(ev.shutil, 'which', return_value='/usr/bin/pdftotext'):
            self.assertEqual(ev._text(b'%PDF-1', 'application/pdf', self.root / 'x'), 'PDF text')
        self.assertTrue(process.stdout.closed)
        process.stdout = None
        process.poll.return_value = None
        with patch.object(ev.shutil, 'which', return_value='/usr/bin/pdftotext'), \
                self.assertRaisesRegex(ev.Rejected, 'stdout unavailable'):
            ev._text(b'%PDF-1', 'application/pdf', self.root / 'x')
        process.kill.assert_called_once()
        self.assertEqual(ev._rewrite('https://github.com/o/r/blob/main/test.js'), 'https://raw.githubusercontent.com/o/r/main/test.js')
        self.assertEqual(ev._rewrite('https://gist.github.com/alice/123'), 'https://gist.githubusercontent.com/alice/123/raw')

    def test_first_public_address_failure_falls_back_without_resolving_again(self):
        addresses = ['2606:4700:4700::1111', '8.8.8.8']
        response = Mock(status=200)
        response.getheader.side_effect = lambda name, default=None: default
        response.read.return_value = b'ok'
        conn, transport = Mock(), Mock()
        conn.getresponse.return_value = response
        with patch.object(ev, '_resolve', return_value=addresses) as resolve, \
                patch.object(ev.socket, 'create_connection', side_effect=[OSError('IPv6 unavailable'), transport]) as connect, \
                patch.object(ev.http.client, 'HTTPConnection', return_value=conn), \
                patch.object(ev.threading, 'Timer') as timer:
            self.assertEqual(self.real_fetch('http://public.org/file')[0], b'ok')
            resolve.assert_called_once()
            self.assertEqual([call.args[0] for call in connect.call_args_list],
                             [(addresses[0], 80), (addresses[1], 80)])
            self.assertTrue(all(0 < call.args[1] <= ev.TIMEOUT for call in connect.call_args_list))
            self.assertIs(conn.sock, transport)
            transport.settimeout.assert_called_once()
            timer.return_value.start.assert_called_once()
            timer.return_value.cancel.assert_called_once()
            abort = timer.call_args.args[1]
            transport.shutdown.side_effect = OSError('already closed')
            abort()
            transport.shutdown.assert_called_once_with(socket.SHUT_RDWR)
            transport.close.assert_called_once()
            connect.reset_mock(side_effect=True)
            connect.side_effect = [OSError('IPv6 unavailable'), OSError('IPv4 unavailable')]
            timer.reset_mock()
            with self.assertRaisesRegex(OSError, 'IPv4 unavailable') as failed:
                self.real_fetch('http://public.org/file')
            self.assertEqual(connect.call_count, 2)
            self.assertEqual(vars(failed.exception)['redirects'], [])
            self.assertEqual(vars(failed.exception)['final_url'], 'http://public.org/file')
            timer.assert_not_called()

    def test_tls_watchdog_targets_wrapped_socket_before_handshake(self):
        raw_socket, tls_socket, context = Mock(), Mock(), Mock()
        context.wrap_socket.return_value = tls_socket
        with patch.object(ev, '_resolve', return_value=['8.8.8.8']), \
                patch.object(ev.socket, 'create_connection', return_value=raw_socket) as connect, \
                patch.object(ev.ssl, 'create_default_context', return_value=context), \
                patch.object(ev.http.client, 'HTTPConnection') as connection, \
                patch.object(ev.threading, 'Timer') as timer, \
                patch.object(ev.time, 'monotonic', side_effect=[100, 101, 103, 104]):
            def handshake():
                tls_socket.settimeout.assert_called_once_with(17)
                timer.return_value.start.assert_called_once()
                timer.call_args.args[1]()
                raise TimeoutError('TLS handshake deadline')
            tls_socket.do_handshake.side_effect = handshake
            with self.assertRaisesRegex(TimeoutError, 'TLS handshake deadline'):
                self.real_fetch('https://public.org/file')
            self.assertEqual(connect.call_args.args[1], 19)
            context.wrap_socket.assert_called_once_with(
                raw_socket, server_hostname='public.org', do_handshake_on_connect=False)
            self.assertEqual(timer.call_args.args[0], 16)
            self.assertTrue(timer.return_value.daemon)
            tls_socket.shutdown.assert_called_once_with(socket.SHUT_RDWR)
            self.assertEqual(tls_socket.close.call_count, 2)  # watchdog and final cleanup
            timer.return_value.cancel.assert_called_once()
            raw_socket.shutdown.assert_not_called()
            raw_socket.close.assert_not_called()
            connection.assert_not_called()

    def test_failed_redirect_context_is_preserved_in_cached_manifest(self):
        response = Mock(status=302)
        response.getheader.side_effect = lambda name, default=None: (
            'http://127.0.0.1/secret' if name == 'Location' else default)
        conn = Mock()
        conn.getresponse.return_value = response
        self.fetch.side_effect = self.real_fetch
        report = self.report('[example](http://public.org/file)')
        with patch.object(ev, '_resolve', return_value=['8.8.8.8']) as resolve, \
                patch.object(ev.socket, 'create_connection', return_value=Mock()), \
                patch.object(ev.http.client, 'HTTPConnection', return_value=conn), \
                patch.object(ev.threading, 'Timer'):
            result = ev.collect(report, self.root)
            resolve.assert_called_once()
            item = result['evidence'][0]
            self.assertEqual(item['status'], 'excluded')
            self.assertEqual(item['final_url'], 'http://127.0.0.1/secret')
            self.assertEqual(item['redirects'], [{'url': 'http://public.org/file', 'status': 302}])
            self.assertEqual(ev.collect(report, self.root), result)
            self.fetch.assert_called_once()

    def test_numeric_socket_tls_and_redirect_revalidation(self):
        # Invoke the real transport only with socket, DNS and TLS fully mocked.
        real_fetch = self.real_fetch
        response = Mock(status=200)
        response.getheader.side_effect = lambda name, default=None: {'Content-Type': 'text/plain'}.get(name, default)
        response.read.return_value = b'ok'
        conn = Mock(); conn.getresponse.return_value = response
        raw_socket, tls_socket, context = Mock(), Mock(), Mock()
        context.wrap_socket.return_value = tls_socket
        with patch.object(ev, '_resolve', return_value=['8.8.8.8']) as resolve, \
                patch.object(ev.socket, 'create_connection', return_value=raw_socket) as connect, \
                patch.object(ev.ssl, 'create_default_context', return_value=context), \
                patch.object(ev.http.client, 'HTTPConnection', return_value=conn):
            self.assertEqual(real_fetch('https://public.org/file')[0], b'ok')
            self.assertEqual(connect.call_args.args[0], ('8.8.8.8', 443))
            context.wrap_socket.assert_called_once_with(
                raw_socket, server_hostname='public.org', do_handshake_on_connect=False)
            tls_socket.do_handshake.assert_called_once()
            tls_socket.settimeout.assert_called_once()
            headers = conn.request.call_args.kwargs['headers']
            self.assertNotIn('Authorization', headers)
            self.assertNotIn('Cookie', headers)
            self.assertIs(conn.sock, tls_socket)
            response.status = 302
            response.getheader.side_effect = lambda name, default=None: 'http://127.0.0.1/secret' if name == 'Location' else default
            with self.assertRaises(ev.Rejected):
                real_fetch('https://public.org/file')
            self.assertEqual(resolve.call_count, 2)  # unsafe redirect never resolves/connects
            response.getheader.side_effect = lambda name, default=None: '/again' if name == 'Location' else default
            with self.assertRaisesRegex(ev.Rejected, 'redirect limit'):
                real_fetch('https://public.org/file')
            response.status = 200
            response.getheader.side_effect = lambda name, default=None: str(ev.MAX_BYTES + 1) if name == 'Content-Length' else default
            with self.assertRaisesRegex(ev.Rejected, '10MiB'):
                real_fetch('https://public.org/file')


if __name__ == '__main__':
    unittest.main()
