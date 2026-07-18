import re
from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
new_ver = sys.argv[1]

files = {
    'backend/veyron/__init__.py': r'__version__\s*=\s*[\'"]"[\'"]',
    'frontend/src-tauri/tauri.conf.json': r'"version":\s*"[^"]+"',
    'frontend/src-tauri/Cargo.toml': r'^version\s*=\s*"[^"]+"',
}

for rel, pattern in files.items():
    fp = root / rel
    text = fp.read_text(encoding='utf-8')
    replacement = lambda m: m.group(0).replace(m.group(1), new_ver)
    # simpler: just replace the version string inside quotes
    if rel == 'backend/veyron/__init__.py':
        text = re.sub(r'__version__\s*=\s*["\'].*["\']', f'__version__ = "{new_ver}"', text)
    elif rel == 'frontend/src-tauri/tauri.conf.json':
        text = re.sub(r'"version":\s*"[^"]+"', f'"version": "{new_ver}"', text)
    elif rel == 'frontend/src-tauri/Cargo.toml':
        text = re.sub(r'^version\s*=\s*"[^"]+"', f'version = "{new_ver}"', text, flags=re.MULTILINE)
    fp.write_text(text, encoding='utf-8')
    print(f'Updated {rel} -> {new_ver}')
