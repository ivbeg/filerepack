"""Render portable format metadata; executable availability belongs to doctor."""

from pathlib import Path

from filerepack.capabilities import format_capabilities


def render():
    lines = ['---', 'title: Format capability registry', '---', '',
             'Generated from `filerepack.format_registry` and the typed capability adapters.', '',
             'Registered writers still require their declared tools, Python extras and ',
             'preservation validators. Protected or unsupported content is refused. ',
             'Use `filerepack doctor --json` for availability on the current machine. ',
             'An inspection-only entry has no registered compression writer.',
             'Registered describes routing. Successful backend create/read qualification ',
             'requires its recorded profile evidence; '
             'complete runtime writer probing remains open.',
             '',
             '| Extension | Family | Adapter | Writer | Validator | Tools | Extra |',
             '| --- | --- | --- | --- | --- | --- | --- |']
    for item in format_capabilities():
        state = ('inspection only' if item.inspection_only else
                 'experimental' if item.experimental else 'registered' if item.writer else 'none')
        tools = ', '.join(item.tools) or 'Python'
        extra = item.extra or ('validation' if item.category == 'image' else '—')
        lines.append(f'| `{item.extension}` | {item.family} | {item.key} | {state} | '
                     f'{"yes" if item.validator else "none"} | {tools} | {extra} |')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    Path('docs/docs/formats/capabilities.md').write_text(render())
