"""Offline tests: no model requests, login or network access."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import codex_runner as runner


class OutputTests(unittest.TestCase):
    def test_exact_schemas_and_order(self):
        row = dict(record_id="a", category="bug")
        for category in ("bug", "no_bug", "change_submission", "unclear"):
            output = dict(row, category=category)
            with self.subTest(category=category):
                self.assertEqual(runner.parse_output(json.dumps(output) + "\n", "type", ["a"]), [output])
        grade = dict(record_id="a", recipe=None, observed=0, expected=1, target="unclear", external="yes")
        self.assertEqual(runner.parse_output(json.dumps(grade), "grade", ["a"]), [grade])
        invalid = [dict(row, extra=1), dict(record_id="b", category="bug"),
                   dict(record_id="a", type="bug"), dict(row, type="bug")]
        invalid += [dict(row, category=value) for value in ("unknown", "not_bug", None, True, 1, [], {})]
        for bad in invalid:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                runner.parse_output(json.dumps(bad), "type", ["a"])
        for key, value in [("recipe", True), ("recipe", 3), ("observed", 2), ("expected", 0.0), ("target", "many"), ("external", False)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                runner.parse_output(json.dumps(dict(grade, **{key: value})), "grade", ["a"])
        for text in ['{"record_id":"a","category":"bug","category":"bug"}', "[]", "```json\n{}\n```", "\n" + json.dumps(row), json.dumps(row) + "\n" + json.dumps(row)]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                runner.parse_output(text, "type", ["a"])
        with self.assertRaises(ValueError):
            runner.parse_output(json.dumps(dict(grade, recipe=float("nan"))), "grade", ["a"])

    def test_record_order_and_duplicate_ids(self):
        text = '\n'.join(json.dumps(dict(record_id=i, category="bug")) for i in ["b", "a"])
        for ids in (["a", "b"], ["a", "a"]):
            with self.assertRaises(ValueError):
                runner.parse_output(text, "type", ids)


class Pipe:
    def __init__(self):
        self.lines = []
    def readline(self):
        return self.lines.pop(0) if self.lines else b''
    def read(self):
        result = b''.join(self.lines)
        self.lines.clear()
        return result
    def close(self):
        pass


class Input:
    def __init__(self, process):
        self.process = process
    def write(self, raw):
        self.process.request(json.loads(raw))
    def flush(self):
        pass
    def close(self):
        pass


class Process:
    def __init__(self, args, **kwargs):
        self.args, self.options = args, kwargs
        self.stdin, self.stdout = Input(self), Pipe()
        self.returncode, self.commands = None, []
        self.efforts, self.model, self.thread_model = ['high', 'max'], runner.MODEL, runner.MODEL
        self.mutate_events = lambda events: events
        self.mutate_state = lambda state: state
        self.turn_count, self.auth_type, self.failed_read = 0, 'chatgpt', False

    def push(self, event):
        self.stdout.lines.append(json.dumps(event, ensure_ascii=False).encode() + b'\n')

    def request(self, request):
        self.commands.append(request)
        method, params = request.get('method'), request.get('params', {})
        result = {}
        if method == 'initialize':
            result = {'userAgent': 'fake'}
        elif method == 'account/read':
            result = {'account': {'type': self.auth_type, 'email': 'PRIVATE_ACCOUNT'}}
        elif method == 'config/read':
            result = {'config': {'mcp_servers': {'example': {'env': {'TOKEN': 'PRIVATE_CONFIG'}}}}}
        elif method == 'model/list':
            result = {'data': [{'model': self.model, 'supportedReasoningEfforts': [{'reasoningEffort': e} for e in self.efforts]}]}
        elif method == 'thread/start':
            self.thread = 'thread-' + params['config']['model_reasoning_effort']
            self.system = params['baseInstructions']
            result = dict(model=self.thread_model, modelProvider=runner.PROVIDER,
                          reasoningEffort=params['config']['model_reasoning_effort'],
                          approvalPolicy='never', sandbox={'type': 'readOnly'}, instructionSources=[],
                          thread=dict(id=self.thread, ephemeral=True, environments=[], turns=[]))
            self.mutate_state(result)
        elif method == 'turn/start':
            self.turn_count += 1
            result = {'turn': {'id': 'turn', 'status': 'inProgress'}}
            self.push(dict(id=request['id'], result=result))
            directory = Path(self.options['cwd'])
            packet = json.loads((directory / 'request.json').read_text())
            events = []
            files = [str(directory / 'request.json')]
            for record in packet['records']:
                files += record.get('files', [])
            for n, path in enumerate(files):
                events.append(dict(id='tool-' + str(n), method='item/tool/call', params=dict(
                    threadId=self.thread, turnId='turn', tool='read_report_file', callId=str(n), arguments={'path': path})))
            rows = []
            for record in packet['records']:
                if params['effort'] == 'high':
                    rows.append(dict(record_id=record['record_id'], category='bug'))
                else:
                    rows.append(dict(record_id=record['record_id'], recipe=2, observed=1, expected=1,
                                     target='single', external='no'))
            events.extend([
                dict(method='item/completed', params=dict(threadId=self.thread, turnId='turn',
                     item=dict(type='agentMessage', id='final', phase='final_answer', text='\n'.join(json.dumps(r) for r in rows)))),
                dict(method='turn/completed', params=dict(threadId=self.thread, turn=dict(id='turn', status='completed', error=None))),
            ])
            for event in self.mutate_events(events):
                self.push(event)
            return
        elif method in ('initialized', None):
            return
        self.push(dict(id=request['id'], result=result))

    def poll(self):
        return self.returncode
    def terminate(self):
        self.returncode = -15
    def kill(self):
        self.returncode = -9
    def wait(self, timeout=None):
        return self.returncode


class RPCTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.record = dict(record_id='a', project='a/b', title='Crash', body='Original text')
        self.processes = []
        self.change = lambda process: None
        def spawn(args, **kwargs):
            p = Process(args, **kwargs)
            self.change(p)
            self.processes.append(p)
            return p
        self.spawn = patch.object(runner.subprocess, 'Popen', side_effect=spawn)
        self.spawn.start()
        self.addCleanup(self.spawn.stop)

    def infer(self, stage='type', record=None):
        return runner.infer(stage, [record or self.record], self.root / 'attempt')

    def receipt(self):
        return json.loads((self.root / 'attempt/receipt.json').read_text())

    def test_codex_round_trip_and_exact_configuration(self):
        self.assertEqual(self.infer(), [dict(record_id='a', category='bug')])
        p = self.processes[0]
        self.assertEqual(p.args[:3], ['codex', 'app-server', '--stdio'])
        start = next(c['params'] for c in p.commands if c.get('method') == 'thread/start')
        self.assertFalse(start['allowProviderModelFallback'])
        self.assertEqual(start['environments'], [])
        self.assertEqual(start['dynamicTools'], [runner.READ_TOOL])
        self.assertFalse(start['config']['mcp_servers.example.enabled'])
        self.assertEqual(start['model'], 'gpt-6-luna')
        self.assertEqual(self.receipt()['state']['thinkingLevel'], 'high')
        self.assertTrue(self.receipt()['read_calls'][0]['success'])
        raw = (self.root / 'attempt/events.jsonl').read_text()
        self.assertNotIn('PRIVATE_ACCOUNT', raw)
        self.assertNotIn('PRIVATE_CONFIG', raw)
        self.assertEqual(self.receipt()['errors'], [])

    def test_grade_reads_text_images_and_lossless_body(self):
        text, picture = self.root / 'evidence.txt', self.root / 'image.png'
        text.write_text('full\r\ntext\u2028end', newline='')
        picture.write_bytes(b'\x89PNG\r\n')
        row = dict(self.record, body='a\u2028b\r\n' * 2000,
                   files=[str(text), str(picture)], optional_files=[])
        self.assertEqual(self.infer('grade', row)[0]['recipe'], 2)
        self.assertEqual(self.receipt()['state']['thinkingLevel'], 'max')
        self.assertEqual(len(self.receipt()['read_calls']), 3)
        replies = [c['result'] for c in self.processes[0].commands if 'result' in c]
        self.assertTrue(any(r['contentItems'][0]['type'] == 'inputImage' for r in replies))
        self.assertTrue(any(r['contentItems'][0].get('text') == 'full\r\ntext\u2028end' for r in replies))
        packet = json.loads((self.root / 'attempt/request.json').read_text())
        self.assertEqual(''.join(packet['records'][0]['body']), row['body'])

    def test_model_effort_login_and_freshness_fail_before_inference(self):
        changes = [lambda p: setattr(p, 'model', 'other'), lambda p: setattr(p, 'efforts', ['high']),
                   lambda p: setattr(p, 'auth_type', 'apiKey'), lambda p: setattr(p, 'thread_model', 'other'),
                   lambda p: setattr(p, 'mutate_state', lambda s: s['thread'].update(ephemeral=False)),
                   lambda p: setattr(p, 'mutate_state', lambda s: s['thread'].update(environments=[{}])),
                   lambda p: setattr(p, 'mutate_state', lambda s: s.update(instructionSources=['unexpected.md']))]
        for n, change in enumerate(changes):
            with self.subTest(n=n):
                self.change = change
                with self.assertRaises(RuntimeError):
                    runner.infer('type', [self.record], self.root / str(n))
                self.assertEqual(self.processes[-1].turn_count, 0)

    def test_check_no_inference_or_private_account_output(self):
        states = runner.check()
        self.assertEqual([s['thinkingLevel'] for s in states], ['high', 'max'])
        self.assertTrue(all(p.turn_count == 0 for p in self.processes))
        self.assertNotIn('PRIVATE', json.dumps(states))

    def test_out_of_scope_read_refused_before_io(self):
        def change(p):
            def mutate(events):
                events[0]['params']['arguments']['path'] = '/not-allowed'
                return events
            p.mutate_events = mutate
        self.change = change
        with self.assertRaisesRegex(RuntimeError, 'out-of-scope'):
            self.infer()
        self.assertEqual(self.receipt()['read_calls'], [])
        self.assertEqual(len(self.processes), 1)

    def test_mandatory_failure_not_turned_into_label(self):
        row = dict(self.record, files=[str(self.root / 'missing.txt')], optional_files=[])
        with self.assertRaisesRegex(RuntimeError, 'mandatory'):
            self.infer('grade', row)
        self.assertTrue(self.receipt()['warnings'])
        self.assertTrue(self.receipt()['final_text'])

    def test_reroute_recovery_tools_and_failed_turn_rejected(self):
        bad = [dict(method='model/rerouted', params={}),
               dict(method='error', params={'willRetry': True}),
               dict(method='codex/event/context_compacted', params={}),
               dict(method='item/started', params=dict(threadId='thread-high', turnId='turn', item={'type': 'commandExecution'})),
               dict(method='turn/completed', params=dict(threadId='thread-high', turn={'id': 'turn', 'status': 'failed', 'error': {}}))]
        for n, event in enumerate(bad):
            with self.subTest(event=event):
                self.change = lambda p: setattr(p, 'mutate_events', lambda events: [event] + events)
                with self.assertRaises(RuntimeError):
                    runner.infer('type', [self.record], self.root / str(n))
                self.assertEqual(self.processes[-1].turn_count, 1)

    def test_invalid_output_preserved_without_retry(self):
        def change(p):
            def mutate(events):
                events[-2]['params']['item']['text'] = 'not JSONL\u2028raw'
                return events
            p.mutate_events = mutate
        self.change = change
        with self.assertRaises(ValueError):
            self.infer()
        self.assertEqual(self.receipt()['final_text'], 'not JSONL\u2028raw')
        self.assertEqual(len(self.processes), 1)

    def test_trailing_truncated_record_saved_and_rejected(self):
        def change(p):
            original_push = p.push
            def push(event):
                original_push(event)
                if event.get('method') == 'turn/completed':
                    p.stdout.lines.append(b'{"truncated":')
            p.push = push
        self.change = change
        with self.assertRaisesRegex(RuntimeError, 'unterminated'):
            self.infer()
        self.assertTrue((self.root / 'attempt/events.jsonl').read_bytes().endswith(b'{"truncated":'))
        self.assertTrue(self.receipt()['errors'])

    def test_startup_failure_and_reused_directory(self):
        with patch.object(runner.subprocess, 'Popen', side_effect=FileNotFoundError('codex')):
            with self.assertRaises(FileNotFoundError):
                self.infer()
        self.assertIn('FileNotFoundError', self.receipt()['errors'][0])
        with self.assertRaises(ValueError):
            self.infer()


if __name__ == '__main__':
    unittest.main()
