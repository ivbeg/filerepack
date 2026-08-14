# -*- coding: utf-8 -*-

"""Helpers to build tiny DICOM files for tests."""

import struct
from typing import List, Optional

from filerepack.dicom import DICM_MAGIC, DICM_OFFSET, TS_EXPLICIT_VR_LE

_LONG_VR = frozenset({
    'OB', 'OD', 'OF', 'OL', 'OV', 'OW', 'SQ', 'SV', 'UC', 'UN', 'UR', 'UT', 'UV',
})

CT_SOP_CLASS = '1.2.840.10008.5.1.4.1.1.2'
TS_JPEG_BASELINE = '1.2.840.10008.1.2.4.50'


def _pack_tag(group: int, element: int, endian: str) -> bytes:
    return struct.pack(endian + 'HH', group, element)


def _pad(vr: str, value: bytes) -> bytes:
    if len(value) % 2 == 0:
        return value
    return value + (b'\x00' if vr == 'UI' else b' ')


def expl_elem(
    group: int, element: int, vr: str, value: bytes, endian: str = '<',
) -> bytes:
    value = _pad(vr, value)
    out = _pack_tag(group, element, endian) + vr.encode('ascii')
    if vr in _LONG_VR:
        out += b'\x00\x00' + struct.pack(endian + 'I', len(value))
    else:
        out += struct.pack(endian + 'H', len(value))
    return out + value


def impl_elem(
    group: int, element: int, value: bytes, endian: str = '<',
) -> bytes:
    if len(value) % 2:
        value += b'\x00'
    return (
        _pack_tag(group, element, endian)
        + struct.pack(endian + 'I', len(value))
        + value
    )


def expl_empty_sq(group: int, element: int, endian: str = '<') -> bytes:
    return (
        _pack_tag(group, element, endian)
        + b'SQ\x00\x00'
        + struct.pack(endian + 'I', 0)
    )


def uid_bytes(uid: str) -> bytes:
    return uid.encode('ascii')


def u16_bytes(n: int, endian: str = '<') -> bytes:
    return struct.pack(endian + 'H', n)


def build_dicom(
    *,
    transfer_syntax: str = TS_EXPLICIT_VR_LE,
    pixel_data: Optional[bytes] = b'\x00' * 32,
    signatures: bool = False,
    extra_dataset: Optional[List[bytes]] = None,
    implicit_dataset: bool = False,
    endian: str = '<',
) -> bytes:
    """Build a Part-10 DICOM with File Meta + a tiny dataset."""
    meta_body = b''.join([
        expl_elem(0x0002, 0x0001, 'OB', b'\x00\x01'),
        expl_elem(0x0002, 0x0002, 'UI', uid_bytes(CT_SOP_CLASS)),
        expl_elem(0x0002, 0x0003, 'UI', uid_bytes('1.2.3.4.5')),
        expl_elem(0x0002, 0x0010, 'UI', uid_bytes(transfer_syntax)),
        expl_elem(0x0002, 0x0012, 'UI', uid_bytes('1.2.826.0.1.3680043.2.1143')),
    ])
    meta = expl_elem(0x0002, 0x0000, 'UL', struct.pack('<I', len(meta_body)))
    meta += meta_body

    ds_parts: List[bytes] = []
    if implicit_dataset:
        ds_parts.append(impl_elem(0x0008, 0x0016, uid_bytes(CT_SOP_CLASS), endian))
        ds_parts.append(impl_elem(0x0008, 0x0018, uid_bytes('1.2.3.4.5'), endian))
        if signatures:
            ds_parts.append(impl_elem(0xFFFA, 0xFFFA, b'', endian))
        if extra_dataset:
            ds_parts.extend(extra_dataset)
        if pixel_data is not None:
            ds_parts.append(impl_elem(0x7FE0, 0x0010, pixel_data, endian))
    else:
        ds_parts.append(
            expl_elem(0x0008, 0x0016, 'UI', uid_bytes(CT_SOP_CLASS), endian),
        )
        ds_parts.append(
            expl_elem(0x0008, 0x0018, 'UI', uid_bytes('1.2.3.4.5'), endian),
        )
        if signatures:
            ds_parts.append(expl_empty_sq(0xFFFA, 0xFFFA, endian))
        if extra_dataset:
            ds_parts.extend(extra_dataset)
        if pixel_data is not None:
            ds_parts.append(
                expl_elem(0x7FE0, 0x0010, 'OW', pixel_data, endian),
            )
    return b'\x00' * DICM_OFFSET + DICM_MAGIC + meta + b''.join(ds_parts)


def image_attrs(endian: str = '<') -> List[bytes]:
    """Rows/columns/bits tags so a real JPEG-LS encoder can run."""
    return [
        expl_elem(0x0028, 0x0002, 'US', u16_bytes(1, endian), endian),
        expl_elem(0x0028, 0x0004, 'CS', b'MONOCHROME2'),
        expl_elem(0x0028, 0x0010, 'US', u16_bytes(8, endian), endian),
        expl_elem(0x0028, 0x0011, 'US', u16_bytes(8, endian), endian),
        expl_elem(0x0028, 0x0100, 'US', u16_bytes(16, endian), endian),
        expl_elem(0x0028, 0x0101, 'US', u16_bytes(16, endian), endian),
        expl_elem(0x0028, 0x0102, 'US', u16_bytes(15, endian), endian),
        expl_elem(0x0028, 0x0103, 'US', u16_bytes(0, endian), endian),
    ]


def encoder_fixture() -> bytes:
    pixels = bytes(b for i in range(8 * 8) for b in (i % 251, 0))
    return build_dicom(
        transfer_syntax=TS_EXPLICIT_VR_LE,
        extra_dataset=image_attrs(),
        pixel_data=pixels,
    )
