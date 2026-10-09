"""Small real PDFs with correct xref offsets; no parser dependency to generate them."""


def pdf_bytes(*, padding=0, text=b'unchanged', marker=b''):
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Count 1 /Kids [3 0 R] >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Resources << >> /Contents 4 0 R >>',
    ]
    content = b'% ' + text + b'\nq Q\n'
    objects.append(b'<< /Length ' + str(len(content)).encode() + b' >>\nstream\n' +
                   content + b'endstream')
    if marker:
        objects.append(marker)  # Deliberately unreferenced protection is still detected.
    result = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    if padding:
        result.extend(b'%' + b' ' * padding + b'\n')
    offsets = [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(str(index).encode() + b' 0 obj\n' + value + b'\nendobj\n')
    xref = len(result)
    result.extend(b'xref\n0 ' + str(len(offsets)).encode() + b'\n0000000000 65535 f \n')
    for offset in offsets[1:]:
        result.extend(f'{offset:010d} 00000 n \n'.encode())
    result.extend(b'trailer\n<< /Size ' + str(len(offsets)).encode() + b' /Root 1 0 R >>\n')
    result.extend(b'startxref\n' + str(xref).encode() + b'\n%%EOF\n')
    return bytes(result)
