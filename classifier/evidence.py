"""Cache-once public reporter evidence. Never infer vagueness from failed collection.

Only report-supplied links are considered; no page crawling or downloaded-code
execution. Snapshots are current, NOT necessarily historical. All output paths
are absolute. Delete a cache deliberately to retry; partial caches fail closed.
"""
from __future__ import annotations

import hashlib
import html
from html.parser import HTMLParser
import http.client
import ipaddress
import io
import json
import os
from pathlib import Path, PurePosixPath
import queue
import re
import shutil
import socket
import ssl
import subprocess
import threading
import time
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
import zipfile

MAX_RESOURCES, MAX_BYTES, TIMEOUT, MAX_REDIRECTS = 20, 10 * 1024**2, 20, 5
TEXT_BUDGET, CHUNK_CHARS, CHUNK_LINES = 40000, 8000, 1000
POLICY = 1
LIMITATION = ('Current public snapshot, not historical evidence; no issue refresh, '
              'comments, fixes, search, authentication or code execution. Collection '
              'failure/unread evidence alone never implies a vague report.')


class Rejected(ValueError):
    pass


class Limited(Rejected):
    pass


def _parts(url):
    p = urlsplit(url)
    if (p.scheme not in ('http', 'https') or not p.hostname or
            p.username is not None or p.password is not None or
            re.search(r'[\x00-\x20\x7f\\]', url)):
        raise Rejected('only credential-free absolute HTTP(S) URLs allowed')
    host = p.hostname.encode('idna').decode().lower().rstrip('.')
    port = p.port if p.port is not None else (443 if p.scheme == 'https' else 80)
    if port != (443 if p.scheme == 'https' else 80):
        raise Rejected('nonstandard port')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise Rejected('IP literal')
    if ('.' not in host or re.fullmatch(r'[0-9.]+', host) or not re.fullmatch(r'[a-z0-9.-]+', host) or
            any(not s or s.startswith('-') or s.endswith('-') for s in host.split('.')) or
            host.rsplit('.', 1)[-1] in ('localhost', 'local', 'internal', 'lan', 'home', 'test', 'invalid', 'onion', 'example')):
        raise Rejected('non-public hostname')
    if any(re.search(r'(token|password|secret|signature|api.?key)', k, re.I)
           for k in p.query.split('&') if '=' in k):
        raise Rejected('credential-like query parameters')
    return p, host, port


def _resolve(host, port, deadline):
    result = queue.Queue()
    def worker():
        try:
            result.put(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
        except Exception as exc:
            result.put(exc)
    threading.Thread(target=worker, daemon=True).start()
    try:
        answer = result.get(timeout=max(.001, deadline - time.monotonic()))
    except queue.Empty:
        raise TimeoutError('DNS resolution deadline exceeded') from None
    if isinstance(answer, Exception):
        raise answer
    addresses = []
    for family, _, _, _, sockaddr in answer:
        ip = ipaddress.ip_address(sockaddr[0])
        if (family not in (socket.AF_INET, socket.AF_INET6) or not ip.is_global or
                ip.is_reserved or ip.is_multicast or getattr(ip, 'ipv4_mapped', None)):
            raise Rejected('DNS returned non-public address')
        addresses.append(str(ip))
    if not addresses:
        raise Rejected('DNS returned no addresses')
    return addresses


def _excluded(url):
    p, host, _ = _parts(url)
    path = unquote(p.path).lower()
    if (re.search(r'/(issues|pulls?|commits?|compare|discussions|comments|answers|solutions)(/|$)', path)
            or re.search(r'issuecomment|discussion_r|pullrequestreview|comment-', p.fragment, re.I)
            or path.endswith(('.patch', '.diff'))):
        return 'issue/PR/commit/comment/fix pages excluded (may contain later solutions)'
    return None


def _fetch(url):
    """Public DNS checked once per hop; numeric TCP pin, TLS uses original host."""
    deadline, chain = time.monotonic() + TIMEOUT, []
    for hop in range(MAX_REDIRECTS + 1):
        conn, sock, timer = None, None, None
        try:
            if reason := _excluded(url):
                raise Rejected(reason)
            p, host, port = _parts(url)
            addresses = _resolve(host, port, deadline)
            # Try every validated numeric address, never resolving the hostname again.
            for index, address in enumerate(addresses):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('connection deadline exceeded')
                try:
                    sock = socket.create_connection((address, port), remaining)
                    break
                except OSError:
                    if index == len(addresses) - 1:
                        raise
            if sock is None:
                raise Rejected('DNS returned no addresses')
            tls_socket = None
            if p.scheme == 'https':
                tls_socket = ssl.create_default_context().wrap_socket(
                    sock, server_hostname=host, do_handshake_on_connect=False)
                sock = tls_socket
            # Wrapping detaches the raw socket. Bind the watchdog to the actual
            # transport and cover the handshake with the remaining hop budget.
            sock.settimeout(max(.001, deadline - time.monotonic()))
            def abort(active_socket=sock):
                try:
                    active_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                active_socket.close()
            timer = threading.Timer(max(.001, deadline - time.monotonic()), abort)
            timer.daemon = True
            timer.start()
            if tls_socket is not None:
                tls_socket.do_handshake()
            conn = http.client.HTTPConnection(host, port, timeout=max(.001, deadline - time.monotonic()))
            conn.sock = sock
            conn.request('GET', urlunsplit(('', '', p.path or '/', p.query, '')),
                         headers={'Host': host, 'User-Agent': 'report-evidence/1', 'Accept-Encoding': 'identity', 'Connection': 'close'})
            response = conn.getresponse()
            chain.append({'url': url, 'status': response.status})
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if not location or hop == MAX_REDIRECTS:
                    raise Rejected('missing redirect target or redirect limit')
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise OSError(f'HTTP {response.status}; redirects={chain!r}')
            if int(response.getheader('Content-Length', '0')) > MAX_BYTES:
                raise Limited('resource exceeds 10MiB')
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise Limited('resource exceeds 10MiB')
            return data, url, response.getheader('Content-Type', ''), chain
        except Exception as exc:
            setattr(exc, 'redirects', chain)
            setattr(exc, 'final_url', url)
            raise
        finally:
            if timer:
                timer.cancel()
            if conn:
                conn.close()
            elif sock:
                sock.close()
    raise Rejected('redirect limit')


def _discover(report):
    found = {}
    for field in ('title', 'body', 'url', 'project'):
        text = str(report.get(field) or '')
        for m in re.finditer(r'https?://[^\s<>"`]+', text, re.I):
            url = html.unescape(m.group().rstrip('.,;!\''))
            while url and url[-1] in ')]}' and url.count(url[-1]) > url.count({')': '(', ']': '[', '}': '{'}[url[-1]]):
                url = url[:-1]
            prefix = text[max(0, m.start() - 150):m.start()]
            context = text[max(0, m.start() - 120):m.end() + 120]
            markdown = bool(re.search(r'!?\[[^\]\n]*\]\(\s*<?$', prefix))
            image = (bool(re.search(r'\.(png|jpe?g|gif|webp)(?:[?#]|$)', url, re.I))
                     or bool(re.search(r'!\[[^\]\n]*\]\(\s*<?$', prefix))
                     or bool(re.search(r"<img\b[^>]*\bsrc\s*=\s*['\"]?$", prefix, re.I)))
            direct = bool(re.search(r'\.(txt|json|js|ts|py|yaml|yml|csv|xml|pdf|zip|md)(?:[?#]|$)', url, re.I))
            snippet = bool(re.match(r'https?://gist\.(github|githubusercontent)\.com/', url, re.I))
            item = found.setdefault(url, {'url': url, 'sources': [], 'preferred': False, 'image': False, 'markdown': False})
            item['sources'].append({'field': field, 'offset': m.start(), 'context': context})
            item['image'] |= image
            item['markdown'] |= markdown
            item['preferred'] |= image or markdown or direct or snippet or bool(re.search(r'repro|demo|example|minimal|attach|screenshot|playground', context, re.I))
    return list(found.values())


def _rewrite(url):
    p, host, _ = _parts(url)
    if host == 'github.com' and '/blob/' in p.path:
        return 'https://raw.githubusercontent.com' + p.path.replace('/blob/', '/', 1)
    if host == 'gist.github.com':
        return urlunsplit(('https', 'gist.githubusercontent.com', p.path.rstrip('/') + '/raw', '', ''))
    return url


def _repo(url, report):
    p, host, _ = _parts(url)
    parts = p.path.strip('/').split('/')
    if host != 'github.com' or len(parts) != 2 or p.query:
        return None
    owner, name = parts[0], parts[1].removesuffix('.git')
    if any(part in ('.', '..') or not re.fullmatch(r'[A-Za-z0-9_.-]+', part)
           for part in (owner, name)):
        raise Rejected('invalid repository name')
    project = str(report.get('project') or '').lower().strip('/')
    if project.startswith(('http://', 'https://')):
        project = urlsplit(project).path.strip('/')
    locator = urlsplit(str(report.get('url') or '')).path.strip('/').split('/')[:2]
    if project in (name.lower(), f'{owner}/{name}'.lower()) or [owner, name] == locator:
        raise Rejected('report main repository is not a reproducer snapshot')
    return owner, name


def _archive(owner, name):
    """Resolve HEAD with isolated git; fetch a commit-pinned archive, not a clone."""
    address = _resolve('github.com', 443, time.monotonic() + TIMEOUT)[0]
    if ':' in address:
        address = f'[{address}]'
    env = {'PATH': os.defpath, 'HOME': '/nonexistent', 'XDG_CONFIG_HOME': '/nonexistent',
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
           'GIT_TERMINAL_PROMPT': '0', 'GIT_ASKPASS': '/bin/false', 'GIT_ALLOW_PROTOCOL': 'https'}
    version = subprocess.run(['git', '--version'], env=env, cwd='/', capture_output=True, timeout=TIMEOUT, check=True)
    match = re.search(rb'git version (\d+)\.(\d+)', version.stdout)
    if not match or tuple(map(int, match.groups())) < (2, 40):
        raise Rejected('git >=2.40 required for supported curloptResolve pinning')
    args = ['git', '-c', 'protocol.version=2', '-c', 'credential.helper=', '-c', 'core.hooksPath=/dev/null',
            '-c', 'http.cookieFile=', '-c', 'http.saveCookies=false',
            '-c', 'http.proxy=', '-c', 'http.followRedirects=false',
            '-c', f'http.curloptResolve=github.com:443:{address}', 'ls-remote',
            f'https://github.com/{owner}/{name}.git', 'HEAD']
    result = subprocess.run(args, env=env, cwd='/', capture_output=True, timeout=TIMEOUT, check=True)
    match = re.fullmatch(rb'([0-9a-f]{40}|[0-9a-f]{64})\s+HEAD\s*', result.stdout)
    if not match:
        raise Rejected('git did not return one pinned HEAD')
    commit = match[1].decode()
    return commit, _fetch(f'https://codeload.github.com/{quote(owner)}/{quote(name)}/zip/{commit}')


class _HTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.text = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        elif tag in ('br', 'p', 'div', 'li', 'pre', 'h1', 'h2'):
            self.text.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)


def _text(data, content_type, raw):
    if data.startswith(b'%PDF-'):
        if not shutil.which('pdftotext'):
            raise Rejected('PDF unread: pdftotext unavailable')
        process = subprocess.Popen(['pdftotext', str(raw), '-'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        timer = threading.Timer(TIMEOUT, process.kill)
        timer.daemon = True
        timer.start()
        stdout = process.stdout
        try:
            if stdout is None:
                raise Rejected('PDF extraction stdout unavailable')
            output = stdout.read(MAX_BYTES + 1)
            if len(output) > MAX_BYTES:
                raise Limited('PDF extracted text exceeds 10MiB')
            if process.wait(timeout=TIMEOUT) != 0:
                raise Rejected('PDF extraction failed/unread')
            return output.decode('utf-8', errors='replace')
        finally:
            timer.cancel()
            if process.poll() is None:
                process.kill()
                process.wait()
            if stdout is not None:
                stdout.close()
    if b'\0' in data or (content_type and not any(t in content_type for t in ('text/', 'json', 'xml', 'javascript'))):
        raise Rejected('unsupported/binary content unread')
    text = data.decode('utf-8', errors='replace')
    if 'html' in content_type or re.match(r'\s*<!doctype html|\s*<html', text, re.I):
        parser = _HTML(); parser.feed(text); text = ''.join(parser.text)
    return text


def _image(data):
    for magic, suffix in ((b'\x89PNG\r\n\x1a\n', 'png'), (b'\xff\xd8\xff', 'jpg'), (b'GIF87a', 'gif'), (b'GIF89a', 'gif')):
        if data.startswith(magic):
            return suffix
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return 'webp'
    return None


def _zip_text(data):
    texts, total = [], 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) > 200 or sum(not z.is_dir() for z in members) > 100:
            raise Limited('archive exceeds 100 files/200 entries')
        for z in members:
            path = PurePosixPath(z.filename)
            mode = z.external_attr >> 16
            if (path.is_absolute() or '..' in path.parts or '\\' in z.filename or re.match(r'^[A-Za-z]:', z.filename) or
                    (mode & 0o170000) == 0o120000 or z.flag_bits & 1):
                raise Rejected('unsafe archive path/symlink/encryption')
            if z.is_dir():
                continue
            total += z.file_size
            if z.file_size > 200 * 1024 or total > 4 * 1024**2 or z.file_size > max(1, z.compress_size) * 1000:
                raise Limited('archive expansion/file size limit')
            value = archive.read(z)
            if b'\0' not in value:
                try:
                    texts.append((z.filename, value.decode('utf-8')))
                except UnicodeDecodeError:
                    pass
    return sorted(texts, key=lambda pair: ('readme' not in pair[0].lower(), pair[0]))


def _chunks(text):
    while text:
        end = min(len(text), CHUNK_CHARS)
        newlines = [m.end() for m in re.finditer('\n', text[:end])]
        if len(newlines) >= CHUNK_LINES:
            end = min(end, newlines[CHUNK_LINES - 1])
        yield text[:end]
        text = text[end:]


def collect(report: dict, root: Path) -> dict:
    """Return evidence metadata, mandatory views and complete optional text parts."""
    serialized = json.dumps(report, sort_keys=True, ensure_ascii=False)
    fingerprint = hashlib.sha256(serialized.encode()).hexdigest()
    directory = Path(root).resolve() / ('evidence-' + fingerprint)
    manifest = directory / 'manifest.json'
    if directory.exists():
        if not manifest.is_file():
            raise RuntimeError(f'interrupted evidence cache (no implicit retry): {directory}')
        try:
            cached = json.loads(manifest.read_text(encoding='utf-8'))
        except (ValueError, OSError) as exc:
            raise RuntimeError('invalid/interrupted evidence cache; explicit reset required') from exc
        if cached.get('fingerprint') != fingerprint or cached.get('policy') != POLICY:
            raise RuntimeError('evidence cache fingerprint/policy mismatch; explicit reset required')
        if not (directory / 'report.json').is_file() or any(not Path(p).is_file() for p in cached['files'] + cached['optional_files'] + cached['raw_files']):
            raise RuntimeError('incomplete evidence cache; explicit reset required')
        return cached
    directory.mkdir(parents=True)
    (directory / 'report.json').write_text(serialized, encoding='utf-8')
    result = {'fingerprint': fingerprint, 'policy': POLICY, 'limitations': LIMITATION,
              'evidence': _discover(report), 'files': [], 'optional_files': [], 'raw_files': []}
    budget, resources, snapshots = TEXT_BUDGET, 0, {}
    for index, item in sorted(enumerate(result['evidence']), key=lambda pair: (not pair[1]['image'], not pair[1]['preferred'], pair[0])):
        item.update(status='not_fetched', limitations=LIMITATION, recorded_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        try:
            url = item['url']
            if url == report.get('url'):
                raise Rejected('report locator: no issue page refresh')
            if reason := _excluded(url):
                raise Rejected(reason)
            host = urlsplit(url).hostname or ''
            incidental = (not item['markdown'] and not item['image'] and
                          bool(re.search(r'registry|pypi|npmjs|rubygems|packagist|nuget', host, re.I)))
            if not item['preferred'] or incidental:
                item['reason'] = 'incidental raw/log/package URL not fetched; may still be needed'
                continue
            repo = _repo(url, report)
            if repo and not re.search(r'repro|demo|example|minimal', json.dumps(item['sources']) + url, re.I):
                raise Rejected('bare repository not identified as a reproducer')
            target = ('repo', *repo) if repo else urlunsplit(urlsplit(_rewrite(url))._replace(fragment=''))
            if target not in snapshots:
                cost = 2 if repo else 1
                if resources + cost > MAX_RESOURCES:
                    item.update(status='limited', reason='20-resource report limit')
                    continue
                resources += cost
                try:
                    snapshots[target] = _archive(*repo) if repo else (None, _fetch(target))
                except Exception as exc:
                    snapshots[target] = exc
            snapshot = snapshots[target]
            if isinstance(snapshot, Exception):
                raise snapshot
            commit, fetched = snapshot
            if commit:
                item['commit'] = commit
            data, final_url, content_type, redirects = fetched
            suffix = _image(data)
            raw = directory / f'{index:03d}.{suffix or "bin"}'
            raw.write_bytes(data)
            result['raw_files'].append(str(raw))
            item.update(status='saved', raw_file=str(raw), sha256=hashlib.sha256(data).hexdigest(),
                        final_url=final_url, fetched_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                        content_type=content_type, bytes=len(data), redirects=redirects)
            if suffix:
                result['files'].append(str(raw))
                item['view_files'] = [str(raw)]
                continue
            zipped = bool(repo) or data.startswith(b'PK\x03\x04')
            texts = _zip_text(data) if zipped else [(url, _text(data, content_type, raw))]
            if zipped:
                item['extraction_limits'] = '100 files, 200KiB/file, 4MiB total; UTF-8 text only; binaries retained only in raw archive'
                item['readme_status'] = 'retained in text_sources' if any('readme' in name.lower() for name, _ in texts) else 'not present as readable text in archive'
                if not texts:
                    raise Rejected('archive unread: no supported UTF-8 text')
            item['text_sources'] = []
            for source_index, (name, text) in enumerate(texts):
                parts = []
                for part, chunk in enumerate(_chunks(text)):
                    path = directory / f'{index:03d}-{source_index:03d}-{part:03d}.txt'
                    path.write_text(chunk, encoding='utf-8', newline='')
                    parts.append(str(path))
                result['optional_files'].extend(parts)
                item['text_sources'].append({'name': name, 'parts': parts, 'characters': len(text)})
                allowance = min(budget, CHUNK_CHARS)
                if not allowance:
                    item['view_limited'] = 'mandatory 40000-character budget; full retained text in optional_files'
                    continue
                marker = '\n\n[END HEAD EXCERPT; middle omitted; BEGIN TAIL EXCERPT; full text in optional_files]\n\n'
                if len(text) > allowance:
                    item['view_limited'] = 'head/tail excerpt; full retained text in optional_files'
                    if allowance <= len(marker):
                        item['view_limited'] = 'mandatory text budget exhausted'
                        continue
                    head = (allowance - len(marker)) // 2
                    view = text[:head] + marker + text[-(allowance - len(marker) - head):]
                else:
                    view = text
                budget -= len(view)
                for part, chunk in enumerate(_chunks(view)):
                    path = directory / f'{index:03d}-{source_index:03d}-view-{part:03d}.txt'
                    path.write_text(chunk, encoding='utf-8', newline='')
                    result['files'].append(str(path))
                    item.setdefault('view_files', []).append(str(path))
        except Exception as exc:
            item.update(status=('limited' if isinstance(exc, Limited) else 'unread' if item.get('raw_file') else
                                'excluded' if isinstance(exc, Rejected) else 'failed'), reason=f'{type(exc).__name__}: {exc}')
            if hasattr(exc, 'redirects'):
                item.update(redirects=getattr(exc, 'redirects'), final_url=getattr(exc, 'final_url', None))
    result['resources_attempted'] = resources
    temporary = directory / 'manifest.tmp'
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(manifest)
    return result
