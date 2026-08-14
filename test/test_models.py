# -*- coding: utf-8 -*-

from filerepack.models import PackResult, RepackSummary


class TestPackResult:
    def test_creation(self):
        result = PackResult(filepath='/test/file.txt', insize=1000, outsize=800, savings_pct=20.0)
        assert result.filepath == '/test/file.txt'
        assert result.insize == 1000
        assert result.outsize == 800
        assert result.savings_pct == 20.0

    def test_savings_bytes(self):
        result = PackResult(filepath='/test/file.txt', insize=1000, outsize=800, savings_pct=20.0)
        assert result.savings_bytes == 200

    def test_savings_bytes_zero(self):
        result = PackResult(filepath='/test/file.txt', insize=1000, outsize=1000, savings_pct=0.0)
        assert result.savings_bytes == 0


class TestRepackSummary:
    def test_empty_creation(self):
        summary = RepackSummary()
        assert summary.results == []
        assert summary.total_insize == 0
        assert summary.total_outsize == 0
        assert summary.elapsed_seconds == 0.0

    def test_total_savings_bytes(self):
        summary = RepackSummary(total_insize=5000, total_outsize=4000)
        assert summary.total_savings_bytes == 1000

    def test_total_savings_pct(self):
        summary = RepackSummary(total_insize=5000, total_outsize=4000)
        assert summary.total_savings_pct == 20.0

    def test_total_savings_pct_zero_insize(self):
        summary = RepackSummary(total_insize=0, total_outsize=0)
        assert summary.total_savings_pct == 0.0

    def test_with_results(self):
        results = [
            PackResult(filepath='a.txt', insize=1000, outsize=800, savings_pct=20.0),
            PackResult(filepath='b.txt', insize=2000, outsize=1500, savings_pct=25.0),
        ]
        summary = RepackSummary(results=results)
        assert len(summary.results) == 2

    def test_legacy_dict_access(self):
        summary = RepackSummary(total_insize=100, total_outsize=80)
        assert 'final' in summary
        assert summary['final'] == [100, 80, 20.0]
        assert summary.get('missing') is None
