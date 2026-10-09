"""Completed independent verification stays bound to the exact files published."""

import hashlib
import os
from dataclasses import replace
from pathlib import Path

import pytest

from filerepack import candidates
from filerepack.transactions import FileSnapshot


def checked_files(tmp_path):
    source = tmp_path / 'source.json'
    candidate = tmp_path / 'candidate.json'
    source.write_bytes(b' { "keep": 1 } ')
    candidate.write_bytes(b'{"keep":1}')
    source.chmod(0o644)
    candidate.chmod(0o644)
    assert candidates.verify_output(str(candidate), 'json')
    assert candidates.verify_preservation(str(source), str(candidate), 'json')
    proof = candidates.VerifiedCandidate(
        'json', FileSnapshot.capture(str(source)), FileSnapshot.capture(str(candidate))
    )
    return source, candidate, proof


@pytest.mark.parametrize('dryrun', [False, True])
def test_completed_verification_is_reused_with_exact_files(tmp_path, monkeypatch, dryrun):
    source, candidate, proof = checked_files(tmp_path)

    def redundant_check(*args, **kwargs):
        pytest.fail('The completed independent check should be reused')

    monkeypatch.setattr(candidates, 'verify_output', redundant_check)
    monkeypatch.setattr(candidates, 'verify_preservation', redundant_check)
    result = candidates.commit_output(
        str(candidate), str(source), source.stat().st_size, verify='json',
        verified=proof, lossless=True, dryrun=dryrun,
    )
    assert result and result.replaced == (not dryrun)
    assert result.outsize == len(b'{"keep":1}')
    assert source.read_bytes() == (b' { "keep": 1 } ' if dryrun else b'{"keep":1}')
    assert not candidate.exists()


@pytest.mark.parametrize('target', ['source', 'candidate'])
@pytest.mark.parametrize('mutation', ['contents', 'inode', 'mode'])
def test_changed_verified_files_are_refused(tmp_path, target, mutation):
    source, candidate, proof = checked_files(tmp_path)
    path = source if target == 'source' else candidate
    prior = path.stat()
    if mutation == 'contents':
        path.write_bytes(path.read_bytes().replace(b'1', b'2'))
        os.utime(path, ns=(prior.st_atime_ns, prior.st_mtime_ns))
    elif mutation == 'inode':
        new = tmp_path / 'replacement'
        new.write_bytes(path.read_bytes())
        os.replace(new, path)
    else:
        path.chmod(0o600)
        if FileSnapshot.capture(str(path)).generation == (
                proof.source if target == 'source' else proof.candidate).generation:
            pytest.skip('Filesystem does not expose this mode change')
    retained = source.read_bytes()
    with pytest.raises(FileExistsError, match='changed'):
        candidates.commit_output(str(candidate), str(source), 15, verify='json',
                                 lossless=True, verified=proof)
    assert source.read_bytes() == retained
    assert not candidate.exists()


@pytest.mark.parametrize('fault', ['kind', 'source', 'candidate'])
def test_verification_for_another_request_is_refused(tmp_path, fault):
    source, candidate, proof = checked_files(tmp_path)
    if fault == 'kind':
        proof = replace(proof, kind='officeart')
    else:
        other = tmp_path / 'other.json'
        other.write_bytes((source if fault == 'source' else candidate).read_bytes())
        proof = replace(proof, **{fault: FileSnapshot.capture(str(other))})
    with pytest.raises(ValueError, match='does not match'):
        candidates.commit_output(str(candidate), str(source), 15, verify='json',
                                 lossless=True, verified=proof)
    assert source.read_bytes() == b' { "keep": 1 } '
    assert not candidate.exists()


@pytest.mark.parametrize('fault', ['source', 'candidate', 'kind'])
def test_worker_evidence_must_match_main_process_bytes(tmp_path, fault):
    from filerepack.ole_recompress import _pack_records

    source = tmp_path / 'source.ppt'
    source.write_bytes(b'source contents')

    def runner(action, original, output, options):
        Path(output).write_bytes(b'candidate')
        proof = {
            'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'candidate_sha256': hashlib.sha256(b'candidate').hexdigest(),
        }
        if fault != 'kind':
            proof[fault + '_sha256'] = '0' * 64
        return {
            'verify': 'ole' if fault == 'kind' else 'officeart',
            'details': {}, 'usage': {}, 'verified_content': proof,
        }

    result = _pack_records(str(source), 'unused', {'dryrun': True}, runner)
    assert result and not result.replaced and result.outsize == source.stat().st_size
    assert 'evidence' in result.reason or 'verification' in result.reason
    assert source.read_bytes() == b'source contents'
