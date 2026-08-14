# -*- coding: utf-8 -*-

import gzip
import json

from filerepack.progress import ProgressReporter, stderr_is_tty
from filerepack.repack import FileRepacker
from filerepack.__main__ import _want_progress, app, _set_output_format, _set_verbosity
from typer.testing import CliRunner

runner = CliRunner()


class TestWantProgress:
    def setup_method(self):
        _set_verbosity(False, False, False)
        _set_output_format(False, False)

    def teardown_method(self):
        _set_verbosity(False, False, False)
        _set_output_format(False, False)

    def test_quiet_disables(self):
        _set_verbosity(True, False, False)
        assert _want_progress(True) is False

    def test_json_disables(self):
        _set_output_format(True, False)
        assert _want_progress(True) is False

    def test_explicit_on(self):
        assert _want_progress(True) is True

    def test_explicit_off(self):
        assert _want_progress(False) is False

    def test_auto_matches_tty(self):
        assert _want_progress(None) is stderr_is_tty()


class TestProgressReporter:
    def test_disabled_is_noop(self):
        messages = []
        bar = ProgressReporter(False, echo=messages.append)
        bar.set_stage("Extracting")
        bar.update(1, name="a.gz")
        bar.close()
        assert messages == []

    def test_text_fallback_interval(self, monkeypatch):
        messages = []
        monkeypatch.setattr(ProgressReporter, "_start_rich", lambda self: None)
        bar = ProgressReporter(True, interval=2, echo=messages.append)
        bar.set_stage("Optimizing", total=4)
        bar.update(1)
        bar.update(2)
        bar.update(3)
        bar.update(4)
        assert messages[0] == "Optimizing..."
        assert "Progress: 2/4 files processed" in messages
        assert "Progress: 4/4 files processed" in messages
        bar.close()

    def test_hook_stages(self, monkeypatch):
        messages = []
        monkeypatch.setattr(ProgressReporter, "_start_rich", lambda self: None)
        bar = ProgressReporter(True, interval=1, echo=messages.append)
        bar.hook("extract")
        bar.hook("files", total=2)
        bar.hook("file", current=1, total=2, name="a.jpg")
        bar.hook("file", current=2, total=2, name="b.jpg")
        bar.hook("write")
        assert messages[0] == "Extracting..."
        assert "Progress: 1/2 files processed" in messages
        assert messages[-1] == "Rewriting..."
        bar.close()

    def test_standalone_hook(self, monkeypatch):
        messages = []
        monkeypatch.setattr(ProgressReporter, "_start_rich", lambda self: None)
        bar = ProgressReporter(True, echo=messages.append)
        bar.hook("standalone", name="/tmp/clip.mp4")
        assert messages == ["Repacking clip.mp4..."]
        bar.close()


class TestRepackProgressCallback:
    def test_standalone_gzip_emits_standalone(self, tmp_path):
        path = tmp_path / "a.gz"
        with gzip.open(path, "wb") as fh:
            fh.write(b"hello" * 50)
        events = []

        def hook(event, **kwargs):
            events.append(event)

        FileRepacker(quiet=True).repack_zip_file(
            str(path), def_options={"quiet": True, "dryrun": True},
            on_progress=hook,
        )
        assert events[0] == "standalone"

    def test_unknown_file_emits_standalone(self, tmp_path):
        path = tmp_path / "notes.txt"
        path.write_text("hello")
        events = []
        FileRepacker(quiet=True).repack_zip_file(
            str(path), def_options={"quiet": True},
            on_progress=lambda event, **kw: events.append(event),
        )
        assert events == ["standalone"]


class TestRepackCLIProgress:
    def test_help_lists_progress(self):
        result = runner.invoke(app, ["repack", "--help"])
        assert result.exit_code == 0
        assert "--progress" in result.output
        assert "--no-progress" in result.output
        assert "--progress-interval" in result.output

    def test_json_stays_clean_with_progress(self, tmp_path):
        path = tmp_path / "a.gz"
        with gzip.open(path, "wb") as fh:
            fh.write(b"hello" * 20)
        result = runner.invoke(
            app, ["repack", str(path), "--json", "--dryrun", "--progress"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["file"] == str(path)

    def test_progress_wires_reporter(self, tmp_path, monkeypatch):
        path = tmp_path / "a.gz"
        with gzip.open(path, "wb") as fh:
            fh.write(b"hello" * 20)
        seen = []

        class FakeBar:
            def __init__(self, enabled, **kwargs):
                seen.append(enabled)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def hook(self, event, **kwargs):
                seen.append(event)

        monkeypatch.setattr("filerepack.__main__.ProgressReporter", FakeBar)
        result = runner.invoke(
            app, ["repack", str(path), "--dryrun", "--progress"]
        )
        assert result.exit_code == 0
        assert True in seen
        assert "standalone" in seen
