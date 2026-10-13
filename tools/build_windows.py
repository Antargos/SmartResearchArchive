"""Build an EXE bundle and per-user installer on a Windows build machine."""

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'artifacts'


def run(*args):
    subprocess.run(list(args), cwd=ROOT, check=True)


def notices(bundle):
    destination = bundle / 'third-party-notices'
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('pypdf', 'cryptography', 'cffi', 'pycparser', 'pyinstaller', 'altgraph',
                 'pyinstaller-hooks-contrib', 'packaging', 'pefile', 'pywin32-ctypes'):
        try:
            distribution = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        for item in distribution.files or []:
            if ('license' in str(item).lower() or 'copying' in str(item).lower()) and distribution.locate_file(item).is_file():
                output = destination / name / str(item).replace('..', '_')
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(distribution.locate_file(item), output)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.exists():
        raise RuntimeError('The Python runtime license is required for distribution.')
    shutil.copyfile(python_license, destination / 'Python-LICENSE.txt')
    for name in ('tcl8.6', 'tk8.6'):
        path = Path(sys.base_prefix) / 'tcl' / name / 'license.terms'
        if path.exists():
            shutil.copyfile(path, destination / f'{name}-license.txt')
    (destination / 'README.txt').write_text(
        'Third-party components retain their own licenses. These notices do not grant a license '
        'to Smart Research Archive. Build-tool notices are also included for completeness.', encoding='utf-8')


def main():
    if sys.platform != 'win32':
        raise RuntimeError('Build the Windows application on Windows.')
    ARTIFACTS.mkdir(exist_ok=True)
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed',
        '--noupx', '--name', 'SmartResearchArchive', '--distpath', str(ROOT / 'dist'),
        '--workpath', str(ROOT / 'build' / 'pyinstaller'), '--specpath', str(ROOT / 'build'),
        '--copy-metadata', 'cryptography', '--copy-metadata', 'pypdf', 'desktop_app.py')
    bundle = ROOT / 'dist' / 'SmartResearchArchive'
    notices(bundle)
    shutil.copyfile(ROOT / 'docs' / 'windows-user-guide.md', bundle / 'Anleitung.md')
    executable = bundle / 'SmartResearchArchive.exe'
    run(str(executable), '--self-test')
    report = ARTIFACTS / 'exe-smoke-test.json'
    run(str(executable), '--smoke-test', '--report', str(report))
    if not report.exists() or not json.loads(report.read_text())['window_created']:
        raise RuntimeError('Packaged GUI startup did not complete.')
    compiler = next((p for p in (
        Path(os.environ.get('ISCC', 'C:/Program Files (x86)/Inno Setup 6/ISCC.exe')),
        Path('C:/Program Files/Inno Setup 6/ISCC.exe')) if p.is_file()), None)
    if compiler is None:
        raise RuntimeError('Install Inno Setup 6.3+ or set ISCC to the compiler path.')
    run(str(compiler), str(ROOT / 'packaging' / 'setup.iss'))
    # Test installation in an isolated build-folder destination, not the user's app.
    installed = ROOT / 'build' / 'installed-smoke'
    setup = ARTIFACTS / 'SmartResearchArchive-1.0.0-Setup.exe'
    run(str(setup), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/TASKS=',
        '/DIR=' + str(installed), '/LOG=' + str(ARTIFACTS / 'installer-test.log'))
    run(str(installed / 'SmartResearchArchive.exe'), '--self-test')
    run(str(installed / 'SmartResearchArchive.exe'), '--smoke-test', '--report', str(ARTIFACTS / 'installed-smoke-test.json'))
    run(str(installed / 'unins000.exe'), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
    archive = shutil.make_archive(str(ARTIFACTS / 'SmartResearchArchive-1.0.0-Portable'), 'zip',
                                  root_dir=ROOT / 'dist', base_dir='SmartResearchArchive')
    files = [setup, Path(archive)]
    checksum_lines = [hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name for path in files]
    (ARTIFACTS / 'SHA256SUMS.txt').write_text('\n'.join(checksum_lines) + '\n', encoding='utf-8')
    (ARTIFACTS / 'build-info.json').write_text(json.dumps(dict(
        version='1.0.0', source_commit=os.environ.get('GITHUB_SHA', 'local'), python=sys.version,
        pyinstaller=importlib.metadata.version('pyinstaller'), packaged_gui_test=True,
        install_uninstall_test=True, live_chatgpt_test=False), indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
