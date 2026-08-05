"""
Установка расширения pgvector в portable PostgreSQL ERGO MS.

Вызов: ergoms package-install pgvector [--force]
       ergoms ai_assistant:install-pgvector [--force]

Только ERGO_DB=portable_postgres и установленный portable Postgres.

Windows: готовые DLL из andreiramani/pgvector_pgsql_windows
  (у официального pgvector/pgvector нет release assets для Windows).
Linux: сборка из исходников официального репозитория.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEPLOYMENT_DIR = PROJECT_ROOT / 'core' / 'deployment'
SCRIPTS_DIR = DEPLOYMENT_DIR / 'scripts'
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(DEPLOYMENT_DIR) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT_DIR))

from console_tags import configure_stdio_utf8, format_console as _fc  # noqa: E402
from postgres_common import (  # noqa: E402
    effective_portable_port,
    is_installed as postgres_is_installed,
    load_db_defaults,
    postgres_bin,
    postgres_packages_dir,
    read_installed_version,
)
from project_layout import cache_tmp_dir, ensure_dir  # noqa: E402

PGVECTOR_VERSION = '0.8.6'
PGVECTOR_GIT_TAG = f'v{PGVECTOR_VERSION}'
WINDOWS_RELEASE_REPO = 'andreiramani/pgvector_pgsql_windows'
DOWNLOAD_USER_AGENT = 'ergoms/1.0 (pgvector installer)'
MARKER_NAME = 'PGVECTOR_INSTALLED'


def pgvector_marker(root: Path) -> Path:
    return postgres_packages_dir(root) / MARKER_NAME


def is_pgvector_installed(root: Path) -> bool:
    return pgvector_marker(root).is_file()


def _postgres_major(version: str) -> int:
    match = re.match(r'(\d+)', (version or '').strip())
    if not match:
        raise RuntimeError(f'Не удалось определить major PostgreSQL из версии: {version!r}')
    return int(match.group(1))


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={'User-Agent': DOWNLOAD_USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response, dest.open('wb') as out:
        shutil.copyfileobj(response, out)


def _github_json(url: str) -> dict | list:
    request = urllib.request.Request(url, headers={'User-Agent': DOWNLOAD_USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode('utf-8'))


def _find_windows_asset_url(pg_major: int) -> str:
    """Найти zip с vector.dll для данного major PostgreSQL."""
    preferred_tag = f'{PGVECTOR_VERSION}_{pg_major}'
    preferred_name = f'vector.v{PGVECTOR_VERSION}-pg{pg_major}.zip'
    direct = (
        f'https://github.com/{WINDOWS_RELEASE_REPO}/releases/download/'
        f'{preferred_tag}/{preferred_name}'
    )
    try:
        request = urllib.request.Request(direct, method='HEAD', headers={'User-Agent': DOWNLOAD_USER_AGENT})
        with urllib.request.urlopen(request, timeout=30):
            return direct
    except (urllib.error.HTTPError, urllib.error.URLError):
        pass

    releases = _github_json(
        f'https://api.github.com/repos/{WINDOWS_RELEASE_REPO}/releases?per_page=40'
    )
    if not isinstance(releases, list):
        raise RuntimeError(f'Неожиданный ответ GitHub API для {WINDOWS_RELEASE_REPO}')

    for release in releases:
        tag = str(release.get('tag_name') or '')
        for asset in release.get('assets') or []:
            name = asset.get('name') or ''
            url = asset.get('browser_download_url') or ''
            if not url or not name.endswith('.zip'):
                continue
            if name.lower() == preferred_name.lower():
                return url
            if f'pg{pg_major}' in name.lower() and PGVECTOR_VERSION in name:
                return url
            if tag.startswith(f'{PGVECTOR_VERSION}_') and f'pg{pg_major}' in name.lower():
                return url

    raise RuntimeError(
        f'Не найден Windows-архив pgvector {PGVECTOR_VERSION} для PostgreSQL {pg_major}. '
        f'Проверьте релизы https://github.com/{WINDOWS_RELEASE_REPO}/releases'
    )


def _install_windows(root: Path, pg_major: int) -> None:
    base = postgres_packages_dir(root)
    lib_dir = base / 'lib'
    ext_dir = base / 'share' / 'extension'
    lib_dir.mkdir(parents=True, exist_ok=True)
    ext_dir.mkdir(parents=True, exist_ok=True)

    cache_tmp = ensure_dir(cache_tmp_dir(root))
    asset_url = _find_windows_asset_url(pg_major)
    print(_fc('info', f'Скачивание {asset_url}'))
    with tempfile.TemporaryDirectory(dir=str(cache_tmp)) as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / 'pgvector.zip'
        _download(asset_url, zip_path)
        extract_dir = tmp_path / 'extract'
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path, 'r') as archive:
            archive.extractall(extract_dir)

        dll_candidates = list(extract_dir.rglob('vector.dll'))
        if not dll_candidates:
            dll_candidates = list(extract_dir.rglob('*.dll'))
        for dll in dll_candidates:
            if dll.name.lower().startswith('vector'):
                shutil.copy2(dll, lib_dir / dll.name)
                break
        else:
            raise RuntimeError('В архиве pgvector не найден vector.dll')

        for control in extract_dir.rglob('vector.control'):
            shutil.copy2(control, ext_dir / control.name)
        for sql_file in extract_dir.rglob('vector--*.sql'):
            shutil.copy2(sql_file, ext_dir / sql_file.name)


def _install_linux(root: Path) -> None:
    pg_config = postgres_bin(root, 'pg_config')
    if not pg_config.is_file():
        raise RuntimeError(f'pg_config не найден: {pg_config}')

    cache_tmp = ensure_dir(cache_tmp_dir(root))
    with tempfile.TemporaryDirectory(dir=str(cache_tmp)) as tmp:
        tmp_path = Path(tmp)
        src_dir = tmp_path / 'pgvector'
        subprocess.run(
            [
                'git', 'clone', '--depth', '1', '--branch', PGVECTOR_GIT_TAG,
                'https://github.com/pgvector/pgvector.git', str(src_dir),
            ],
            check=True,
        )
        env = os.environ.copy()
        env['PG_CONFIG'] = str(pg_config)
        subprocess.run(['make'], cwd=str(src_dir), env=env, check=True)
        subprocess.run(['make', 'install'], cwd=str(src_dir), env=env, check=True)


def _create_extension(root: Path) -> None:
    defaults = load_db_defaults(root)
    port = effective_portable_port(root)
    host = defaults.get('host') or '127.0.0.1'
    user = defaults['user']
    dbname = defaults['name']
    psql = postgres_bin(root, 'psql')
    env = {
        **os.environ,
        'PGUSER': user,
        'PGPASSWORD': defaults['password'],
        'PGHOST': host,
        'PGPORT': str(port),
    }
    # Явные -h/-U: иначе на Windows psql может уйти не в portable-инстанс.
    subprocess.run(
        [
            str(psql), '-v', 'ON_ERROR_STOP=1',
            '-h', host, '-p', str(port), '-U', user, '-d', dbname,
            '-c', 'CREATE EXTENSION IF NOT EXISTS vector;',
        ],
        env=env,
        check=True,
    )


def install_pgvector(root: Path, *, force: bool = False) -> int:
    configure_stdio_utf8()

    try:
        from deployment_env import get_ergo_db
    except ImportError:
        get_ergo_db = lambda: 'portable_postgres'  # noqa: E731

    db_mode = get_ergo_db()
    if db_mode != 'portable_postgres':
        print(_fc('skip', f'ERGO_DB={db_mode}: установка pgvector только для portable_postgres'))
        return 0

    if not postgres_is_installed(root):
        print(_fc('error', 'Portable PostgreSQL не установлен. Выполните: ergoms install-postgres'))
        return 1

    if is_pgvector_installed(root) and not force:
        print(_fc('skip', 'pgvector уже установлен в portable PostgreSQL'))
        return 0

    version = read_installed_version(root) or '17.0'
    pg_major = _postgres_major(version)
    system = platform.system().lower()

    try:
        if system == 'windows':
            _install_windows(root, pg_major)
        elif system == 'linux':
            _install_linux(root)
        else:
            print(_fc('error', f'Неподдерживаемая платформа для pgvector: {system}'))
            return 1

        _create_extension(root)
        marker = pgvector_marker(root)
        marker.write_text(f'{PGVECTOR_VERSION}\npg{pg_major}\n', encoding='utf-8')
        print(_fc('ok', f'pgvector {PGVECTOR_VERSION} установлен (PostgreSQL {version})'))
        return 0
    except subprocess.CalledProcessError as exc:
        print(_fc('error', f'Ошибка установки pgvector: {exc}'))
        return 1
    except Exception as exc:
        print(_fc('error', str(exc)))
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description='Установка pgvector в portable PostgreSQL')
    parser.add_argument('--force', action='store_true', help='Переустановить pgvector')
    parser.add_argument('--root', type=Path, default=PROJECT_ROOT, help='Корень проекта ERGO MS')
    args = parser.parse_args()
    return install_pgvector(args.root.resolve(), force=args.force)


if __name__ == '__main__':
    raise SystemExit(main())
