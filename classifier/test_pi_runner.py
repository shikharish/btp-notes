"""API-free protocol tests: all subprocesses and prompt reads are mocked."""
import copy
from collections import deque
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import pi_runner as runner
except ImportError:
    import pi_runner as runner


def assistant(text="", **changes):
    message = dict(role="assistant", provider=runner.PROVIDER, model=runner.MODEL,
                   thinkingLevel="high", providerThinkingLevel="high", usage={"input": 3, "output": 2},
                   stopReason="stop", content=[dict(type="text", text=text)])
    message.update(changes)
    return message


class Pipe:
    """A binary LF-only fake stdout; never interpret Unicode line separators."""
    def __init__(self):
        self.lines = deque()

    def add(self, event):
        self.lines.append(json.dumps(event, ensure_ascii=False).encode() + b"\n")

    def readline(self):
        return self.lines.popleft() if self.lines else b""

    def __iter__(self):
        while self.lines:
            yield self.readline()

    def close(self):
        pass


class Input:
    def __init__(self, process):
        self.process = process

    def write(self, raw):
        self.process.receive(json.loads(raw))
        return len(raw)

    def flush(self):
        pass

    def close(self):
        self.process.returncode = self.process.returncode or 0


class Process:
    """Reactive RPC peer. No actual Pi process or model can run in these tests."""
    def __init__(self, args, **options):
        self.args, self.options = args, options
        self.level = args[args.index("--thinking") + 1]
        self.system_path = Path(args[args.index("--system-prompt") + 1])
        self.system = self.system_path.read_text(encoding="utf-8")
        self.category = "bug"
        self.stdout, self.stdin = Pipe(), Input(self)
        self.returncode, self.killed, self.commands = None, False, []
        self.mutate_state = lambda state: None
        self.mutate_events = lambda events: events
        self.bad_response = False

    def receive(self, command):
        self.commands.append(command)
        kind, data = command["type"], None
        if kind == "get_state":
            data = dict(model=dict(provider=runner.PROVIDER, id=runner.MODEL), thinkingLevel=self.level,
                        messageCount=0, pendingMessageCount=0, isStreaming=False, isCompacting=False,
                        autoCompactionEnabled=False, sessionFile=None, sessionId="new-" + self.level)
            self.mutate_state(data)
        if kind == "prompt":
            data = dict(disposition="started")
        self.stdout.add(dict(type="response", command=kind, id="wrong" if self.bad_response else command["id"], success=True, data=data))
        if kind == "prompt":
            directory = self.options["cwd"]
            packet_path = directory / "request.json"
            packet = json.loads(packet_path.read_text())
            rows = packet["records"]
            paths = [str(packet_path)] + [p for row in rows for p in row.get("files", [])]
            events = []
            for index, path in enumerate(paths):
                events += [dict(type="tool_execution_start", toolCallId=str(index), toolName="read", args=dict(path=path)),
                           dict(type="tool_execution_end", toolCallId=str(index), toolName="read", isError=False, result={})]
            output = [dict(record_id=row["record_id"], category=self.category) if self.level == "high" else
                      dict(record_id=row["record_id"], recipe=2, observed=1, expected=None, target="single", external="no") for row in rows]
            text = "\n".join(json.dumps(row) for row in output)
            message = assistant(text, thinkingLevel=self.level, providerThinkingLevel=self.level)
            events += [dict(type="message_end", message=message), dict(type="turn_end", message=message),
                       dict(type="agent_end", messages=[message], willRetry=False), dict(type="agent_settled", aborted=False)]
            for event in self.mutate_events(events):
                self.stdout.add(event)

    def poll(self):
        return self.returncode

    def wait(self):
        self.returncode = self.returncode or 0
        return self.returncode

    def kill(self):
        self.killed, self.returncode = True, -9


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


class RPCTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.processes, self.change = [], lambda process: None
        self.record = dict(record_id="a", project="project", title="title", body="body")
        self.real_read = Path.read_text

        def read(path, *args, **kwargs):
            if path.name in ("bug.md", "vagueness.md"):
                return "Trusted prompt for " + path.name
            return self.real_read(path, *args, **kwargs)

        def spawn(args, **kwargs):
            process = Process(args, **kwargs)
            self.change(process)
            self.processes.append(process)
            return process

        self.spawn = patch.object(runner.subprocess, "Popen", side_effect=spawn)
        self.prompts = patch.object(Path, "read_text", read)
        self.spawn.start()
        self.prompts.start()
        self.addCleanup(self.spawn.stop)
        self.addCleanup(self.prompts.stop)
        self.addCleanup(self.temporary.cleanup)

    def infer(self, stage="type", record=None):
        return runner.infer(stage, [record or self.record], self.root / "attempt")

    def receipt(self):
        return json.loads((self.root / "attempt" / "receipt.json").read_text())

    def mutate(self, function):
        self.change = lambda process: setattr(process, "mutate_events", function)

    def test_success_flags_state_before_prompt_and_packet_privacy(self):
        record = dict(self.record, body="a\u2028b\r\n" * 2000, url="SECRET_URL", category="cached", grades={"recipe": 2})
        with patch.dict(runner.os.environ, {"PI_SESSION_FILE": "parent", "PI_SESSION_ID": "old", "NORMAL_AUTH_ENV": "unchanged"}):
            self.assertEqual(self.infer(record=record), [dict(record_id="a", category="bug")])
        process = self.processes[0]
        self.assertEqual([c["type"] for c in process.commands], ["set_auto_retry", "set_auto_compaction", "get_state", "prompt"])
        self.assertNotIn("PI_SESSION_ID", process.options["env"])
        self.assertNotIn("PI_SESSION_FILE", process.options["env"])
        self.assertEqual(process.options["env"]["NORMAL_AUTH_ENV"], "unchanged")
        for flag in ("--no-session", "--offline", "--no-extensions", "--no-mcp", "--no-context-files", "--no-skills", "--no-prompt-templates", "--no-approve"):
            self.assertIn(flag, process.args)
        self.assertEqual(process.args[process.args.index("--tools") + 1], "read")
        self.assertEqual(process.system_path, self.root / "attempt" / "system.md")
        system = process.system
        self.assertEqual(self.receipt()["system_prompt"], system)
        self.assertEqual(self.receipt()["prompt"], "Read the packet at " + str(self.root / "attempt" / "request.json") + ". Perform only the trusted stage task.")
        self.assertIn('Exactly two keys: record_id, category. category is one of ["bug", "no_bug", "change_submission", "unclear"]', system)
        self.assertIn("Trusted prompt for bug.md", system)
        self.assertNotIn("vagueness.md", system)
        self.assertNotIn("Exactly six keys", system)
        row = json.loads((self.root / "attempt" / "request.json").read_text())["records"][0]
        self.assertEqual(set(row), set(runner.FIELDS["type"]))
        self.assertEqual("".join(row["body"]), record["body"])
        self.assertTrue(all(len(chunk) <= 4000 for chunk in row["body"]))
        self.assertTrue(all((self.root / "attempt" / name).exists() for name in ["request.json", "system.md", "events.jsonl", "stderr.log", "receipt.json"]))
        self.assertEqual(self.receipt()["errors"], [])
        self.assertEqual(len(self.receipt()["responses"]), 1)
        self.assertTrue(self.receipt()["read_calls"][0]["success"])

    def test_no_bug_and_change_submission_round_trip(self):
        for category in ("no_bug", "change_submission"):
            with self.subTest(category=category), tempfile.TemporaryDirectory() as directory:
                self.change = lambda process: setattr(process, "category", category)
                result = runner.infer("type", [self.record], Path(directory) / "attempt")
                self.assertEqual(result, [dict(record_id="a", category=category)])

    def test_large_evidence_scope_uses_system_prompt_file(self):
        paths = [str(self.root / (str(index) + "x" * 100)) for index in range(2000)]
        self.infer("grade", dict(self.record, files=[], optional_files=paths))
        process = self.processes[0]
        self.assertGreater(len(process.system.encode("utf-8")), 128 * 1024)
        self.assertTrue(all(len(arg.encode("utf-8")) < 128 * 1024 for arg in process.args))
        self.assertEqual(process.system_path, self.root / "attempt" / "system.md")
        self.assertEqual(process.system_path.read_text(encoding="utf-8"), self.receipt()["system_prompt"])
        self.assertIn(json.dumps(sorted(paths + [str(self.root / "attempt" / "request.json")])), process.system)
        self.assertNotIn(str(process.system_path), process.system)

    def test_grade_mandatory_optional_failure_and_extra_eof_are_warnings(self):
        evidence = self.root / "snapshot.txt"
        evidence.write_text("snapshot")
        record = dict(self.record, url="url", evidence={}, files=[str(evidence)], optional_files=[str(self.root / "missing")], category="cached")

        def errors(events):
            for index, path in enumerate((str(evidence), str(self.root / "missing")), 50):
                events[4:4] = [dict(type="tool_execution_start", toolCallId=str(index), toolName="read", args=dict(path=path, offset=999)),
                               dict(type="tool_execution_end", toolCallId=str(index), toolName="read", isError=True, result={"content": [{"type": "text", "text": "EOF or unavailable"}]})]
            return events
        self.mutate(errors)
        self.assertEqual(self.infer("grade", record)[0]["recipe"], 2)
        self.assertEqual(len(self.receipt()["warnings"]), 2)
        self.assertEqual([c["success"] for c in self.receipt()["read_calls"]].count(False), 2)
        self.assertEqual(self.receipt()["state"]["thinkingLevel"], "max")
        self.assertNotIn("Exactly two keys", self.processes[0].system)
        self.assertIn("Trusted prompt for vagueness.md", self.processes[0].system)
        self.assertIn("Exactly six keys", self.processes[0].system)
        self.assertEqual(self.receipt()["system_prompt"], self.processes[0].system)

    def test_missing_mandatory_read_is_fatal_even_with_valid_output(self):
        self.mutate(lambda events: [dict(event, isError=True) if event["type"] == "tool_execution_end" else event for event in events])
        with self.assertRaisesRegex(RuntimeError, "mandatory"):
            self.infer()
        self.assertTrue(self.receipt()["warnings"])
        self.assertTrue(self.receipt()["final_text"])
        self.assertTrue(self.processes[0].killed)

    def test_model_thinking_and_fresh_state_fail_before_prompt(self):
        for key, value in [("thinkingLevel", "medium"), ("sessionFile", "/old"), ("messageCount", 1), ("autoCompactionEnabled", True)]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                self.change = lambda process: setattr(process, "mutate_state", lambda state: state.update({key: value}))
                with self.assertRaises(RuntimeError):
                    runner.infer("type", [self.record], Path(directory) / "attempt")
                self.assertNotIn("prompt", [c["type"] for c in self.processes[-1].commands])
                self.assertTrue(self.processes[-1].killed)

    def test_non_object_state_rejected_before_prompt(self):
        original = runner._RPC.command
        for value in (None, [], "invalid"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                def command(rpc, kind, **args):
                    data = original(rpc, kind, **args)
                    return value if kind == "get_state" else data

                with patch.object(runner._RPC, "command", command):
                    with self.assertRaisesRegex(RuntimeError, "state is not an object"):
                        runner.infer("type", [self.record], Path(directory) / "attempt")
                self.assertNotIn("prompt", [c["type"] for c in self.processes[-1].commands])
                self.assertTrue(self.processes[-1].killed)

    def test_every_authoritative_assistant_report_verified(self):
        for kind in ("message_end", "turn_end", "agent_end"):
            for change in (dict(model="other"), dict(provider="other"), dict(responseModel="other"), dict(thinkingLevel="max"), dict(providerThinkingLevel="max"), dict(stopReason="error"), dict(stopReason="aborted")):
                with self.subTest(kind=kind, change=change), tempfile.TemporaryDirectory() as directory:
                    def bad(events):
                        events = copy.deepcopy(events)
                        event = next(e for e in events if e["type"] == kind)
                        message = event["messages"][0] if kind == "agent_end" else event["message"]
                        message.update(change)
                        return events
                    self.mutate(bad)
                    with self.assertRaises(RuntimeError):
                        runner.infer("type", [self.record], Path(directory) / "attempt")
                    self.assertTrue(self.processes[-1].killed)

    def test_reject_recovery_abort_and_out_of_scope_tools(self):
        events = [dict(type=kind) for kind in ("auto_retry_start", "summarization_retry_scheduled", "compaction_start", "extension_error")]
        events += [dict(type="agent_settled", aborted=True), dict(type="agent_end", willRetry=True),
                   dict(type="tool_execution_start", toolCallId="bad", toolName="bash", args={}),
                   dict(type="tool_execution_start", toolCallId="bad", toolName="read", args=dict(path="/not-listed")),
                   dict(type="message_end", message=assistant(content=[dict(type="toolCall", id="bad", name="read", arguments=dict(path="/not-listed"))]))]
        for event in events:
            with self.subTest(event=event), tempfile.TemporaryDirectory() as directory:
                self.mutate(lambda original: [event] + original)
                with self.assertRaises(RuntimeError):
                    runner.infer("type", [self.record], Path(directory) / "attempt")
                self.assertTrue(self.processes[-1].killed)

    def test_binary_lf_unicode_separators_and_raw_events(self):
        self.mutate(lambda events: [dict(type="message_update", assistantMessageEvent=dict(type="text_delta", delta="x\u2028y\u2029z"))] + events)
        self.infer()
        raw = (self.root / "attempt" / "events.jsonl").read_bytes()
        self.assertIn("x\u2028y\u2029z".encode(), raw)

    def test_check_never_prompts_and_sanitizes_state(self):
        with patch.object(runner.subprocess, "run", return_value=type("Result", (), {"returncode": 0, "stdout": b"PRIVATE", "stderr": b"PRIVATE"})()) as auth:
            states = runner.check()
        self.assertEqual(auth.call_args.args[0], ["pi", "auth", "check", "--provider", runner.PROVIDER, "--json"])
        self.assertEqual(auth.call_args.kwargs["stdout"], runner.subprocess.PIPE)
        self.assertEqual(auth.call_args.kwargs["stderr"], runner.subprocess.PIPE)
        self.assertNotIn("PRIVATE", json.dumps(states))
        self.assertTrue(all(process.system == "No inference. Do not call tools." for process in self.processes))
        self.assertEqual([state["thinkingLevel"] for state in states], ["high", "max"])
        self.assertTrue(all("model" not in state or isinstance(state["model"], str) for state in states))
        self.assertTrue(all(c["type"] != "prompt" for process in self.processes for c in process.commands))
        with patch.object(runner.subprocess, "run", return_value=type("Result", (), {"returncode": 1, "stdout": b"PRIVATE", "stderr": b"PRIVATE"})()):
            with self.assertRaises(RuntimeError) as error:
                runner.check()
        self.assertEqual(str(error.exception), "Pi backend authentication unavailable")

    def test_protocol_failure_no_retry_and_raw_output_preserved(self):
        def bad_jsonl(events):
            events = copy.deepcopy(events)
            for event in events:
                if event["type"] == "message_end":
                    event["message"]["content"] = [dict(type="text", text="not JSONL\u2028still one line")]
            return events
        self.mutate(bad_jsonl)
        with self.assertRaises(ValueError):
            self.infer()
        self.assertEqual(self.receipt()["final_text"], "not JSONL\u2028still one line")
        self.assertEqual(len(self.processes), 1)
        self.assertEqual(self.processes[0].returncode, 0)

    def test_bad_command_response_and_truncated_protocol(self):
        for change in (lambda p: setattr(p, "bad_response", True),
                       lambda p: p.stdout.lines.append(b'{"type":"agent_start"}')):
            with tempfile.TemporaryDirectory() as directory:
                self.change = change
                with self.assertRaises(RuntimeError):
                    runner.infer("type", [self.record], Path(directory) / "attempt")
                self.assertTrue(self.processes[-1].killed)

    def test_work_after_settled_rejected(self):
        self.mutate(lambda events: events + [dict(type="agent_start")])
        with self.assertRaisesRegex(RuntimeError, "after agent_settled"):
            self.infer()
        self.assertTrue(self.receipt()["errors"])

    def test_close_preserves_allowed_trailing_events(self):
        trailing = [dict(type="queue_update", text="x\u2028y\u2029z"), dict(type="session_info_changed")]
        self.mutate(lambda events: events + trailing)
        self.infer()
        raw = (self.root / "attempt" / "events.jsonl").read_bytes()
        self.assertTrue(raw.endswith(b"".join(json.dumps(event, ensure_ascii=False).encode() + b"\n" for event in trailing)))
        self.assertEqual(self.receipt()["errors"], [])

    def test_close_preserves_truncated_raw_record_on_success_and_failure(self):
        for failed in (False, True):
            with self.subTest(failed=failed):
                directory = self.root / str(failed)
                directory.mkdir()
                rpc = runner._RPC(directory, "high", "No inference.", runner._receipt())
                records = [b'{"type":"queue_update"}\n', '{"text":"x\u2028y\u2029z"'.encode()]
                self.processes[-1].stdout.lines.extend(records)
                if failed:
                    rpc.close(failed=True)
                else:
                    with self.assertRaisesRegex(RuntimeError, "unterminated protocol record"):
                        rpc.close()
                self.assertEqual((directory / "events.jsonl").read_bytes(), b"".join(records))
                self.assertEqual(self.processes[-1].killed, failed)
                self.assertIsNotNone(self.processes[-1].returncode)

    def test_startup_failure_preserves_receipt(self):
        with patch.object(runner.subprocess, "Popen", side_effect=FileNotFoundError("pi")):
            with self.assertRaises(FileNotFoundError):
                self.infer()
        self.assertIn("FileNotFoundError", self.receipt()["errors"][0])
        self.assertEqual(self.processes, [])

    def test_reused_directory_and_job_limit_rejected(self):
        with self.assertRaises(ValueError):
            runner.infer("type", [self.record] * 11, self.root / "too-many")
        self.infer()
        with self.assertRaises(ValueError):
            self.infer()
        self.assertEqual(len(self.processes), 1)


if __name__ == "__main__":
    unittest.main()
