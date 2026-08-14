# -*- coding: utf-8 -*-

from filerepack.install_hints import (
    choose_managers, detect_system, format_install_instructions,
    install_command, linux_family,
)
from filerepack.tools import TOOL_SPECS, doctor_rows, install_instructions


DEBIAN_OS_RELEASE = '''
ID=ubuntu
ID_LIKE=debian
'''

FEDORA_OS_RELEASE = '''
ID=fedora
'''

ARCH_OS_RELEASE = '''
ID=arch
'''


class TestDetectSystem:
    def test_macos(self):
        assert detect_system('darwin') == 'macos'

    def test_windows(self):
        assert detect_system('win32') == 'windows'

    def test_linux(self):
        assert detect_system('linux') == 'linux'

    def test_other(self):
        assert detect_system('freebsd') == 'other'


class TestLinuxFamily:
    def test_ubuntu(self):
        assert linux_family(DEBIAN_OS_RELEASE) == 'debian'

    def test_fedora(self):
        assert linux_family(FEDORA_OS_RELEASE) == 'fedora'

    def test_arch(self):
        assert linux_family(ARCH_OS_RELEASE) == 'arch'

    def test_alpine(self):
        assert linux_family('ID=alpine\n') == 'alpine'

    def test_opensuse(self):
        assert linux_family('ID=opensuse-tumbleweed\nID_LIKE="suse"\n') == 'suse'


class TestInstallCommand:
    def test_macos_brew_jpegoptim(self):
        cmd = install_command('jpegoptim', system='macos', manager='brew')
        assert cmd == 'brew install jpegoptim'

    def test_debian_apt_szip(self):
        cmd = install_command('szip', system='linux', manager='apt')
        assert cmd == 'sudo apt-get install p7zip-full'

    def test_windows_choco_ffmpeg(self):
        cmd = install_command('ffmpeg', system='windows', manager='choco')
        assert cmd == 'choco install ffmpeg -y'

    def test_svgo_falls_back_to_npm(self):
        cmd = install_command('svgo', system='linux', manager='apt')
        assert cmd == 'npm install -g svgo'

    def test_scour_falls_back_to_pip(self):
        cmd = install_command('scour', system='macos', manager='brew')
        assert cmd == 'pip install scour'

    def test_mac_is_manual_url(self):
        cmd = install_command('mac', system='macos', manager='brew')
        assert 'monkeysaudio.com' in cmd

    def test_mp3packer_is_manual_url(self):
        cmd = install_command('mp3packer', system='macos', manager='brew')
        assert 'github.com/Snesnopic/mp3packer/releases' in cmd
        assert 'not packaged' in cmd

    def test_debian_apt_gdcmconv(self):
        cmd = install_command('gdcmconv', system='linux', manager='apt')
        assert cmd == 'sudo apt-get install libgdcm-tools'

    def test_windows_choco_dcmcjpls(self):
        cmd = install_command('dcmcjpls', system='windows', manager='choco')
        assert cmd == 'choco install dcmtk -y'


class TestFormatInstallInstructions:
    def test_empty(self):
        assert format_install_instructions([]) == ''

    def test_macos_brew_groups_packages(self):
        text = format_install_instructions(
            ['jpegoptim', 'pngquant', 'oxipng'],
            system='macos',
            managers=('brew', 'ports'),
        )
        assert 'macOS' in text
        assert 'brew install jpegoptim pngquant oxipng' in text
        assert 'sudo port install jpegoptim pngquant oxipng' in text

    def test_dedupes_shared_package(self):
        text = format_install_instructions(
            ['dwebp', 'cwebp'],
            system='macos',
            managers=('brew',),
        )
        assert text.count('webp') == 1
        assert 'brew install webp' in text

    def test_debian_apt(self):
        text = format_install_instructions(
            ['szip', 'qpdf', 'ffmpeg'],
            system='linux',
            managers=('apt',),
        )
        assert 'Linux (Debian/Ubuntu)' in text
        assert 'sudo apt-get install p7zip-full qpdf ffmpeg' in text

    def test_fedora_dnf(self):
        text = format_install_instructions(
            ['szip', 'dwebp'],
            system='linux',
            managers=('dnf',),
        )
        assert 'sudo dnf install p7zip p7zip-plugins libwebp-tools' in text

    def test_arch_pacman(self):
        text = format_install_instructions(
            ['szip', 'ffmpeg'],
            system='linux',
            managers=('pacman',),
        )
        assert 'sudo pacman -S p7zip ffmpeg' in text

    def test_windows_choco_and_winget(self):
        text = format_install_instructions(
            ['szip', 'ffmpeg'],
            system='windows',
            managers=('choco', 'winget', 'scoop'),
        )
        assert 'Windows' in text
        assert 'choco install 7zip ffmpeg -y' in text
        assert 'winget install 7zip.7zip Gyan.FFmpeg' in text
        assert 'scoop install 7zip ffmpeg' in text

    def test_npm_and_pip_extras(self):
        text = format_install_instructions(
            ['svgo', 'scour'],
            system='linux',
            managers=('apt',),
        )
        assert 'npm install -g svgo' in text
        assert 'sudo apt-get install python3-scour' in text or 'pip install scour' in text

    def test_manual_url_when_not_in_brew(self):
        text = format_install_instructions(
            ['unrar', 'mac', 'mp3packer'],
            system='macos',
            managers=('brew',),
        )
        assert 'rarlab.com' in text
        assert 'monkeysaudio.com' in text
        assert 'github.com/Snesnopic/mp3packer/releases' in text
        assert 'not packaged' in text
        assert 'Manual install:' in text

    def test_unknown_os_shows_major_managers(self):
        text = format_install_instructions(
            ['jpegoptim'],
            system='other',
            managers=(),
        )
        assert 'brew install jpegoptim' in text
        assert 'sudo apt-get install jpegoptim' in text
        assert 'choco install jpegoptim -y' in text


class TestChooseManagers:
    def test_explicit_managers(self):
        primary, alts = choose_managers('macos', managers=('ports', 'brew'))
        assert primary == 'ports'
        assert alts == ['brew']


class TestDoctorRowsInstall:
    def test_dicom_tools_optional_with_purpose(self):
        specs = {spec.key: spec for spec in TOOL_SPECS}
        assert specs['gdcmconv'].required is False
        assert specs['dcmcjpls'].required is False
        assert 'DICOM' in specs['gdcmconv'].purpose
        assert 'DICOM' in specs['dcmcjpls'].purpose

    def test_every_spec_has_install_mapping_or_ok_path(self):
        keys = {spec.key for spec in TOOL_SPECS}
        from filerepack.install_hints import PACKAGES
        assert keys <= set(PACKAGES)

    def test_install_field_present(self):
        rows = doctor_rows()
        assert rows
        for row in rows:
            assert 'install' in row
            if row['path']:
                assert row['install'] == ''

    def test_install_instructions_wrapper(self):
        text = install_instructions(
            ['jpegoptim'], system='macos', managers=('brew',),
        )
        assert 'brew install jpegoptim' in text
