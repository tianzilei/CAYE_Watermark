# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CAYE Watermark WebUI.

Build with:
    pyinstaller caye-watermark-web.spec

Or use the Makefile:
    make build
"""
import os
import sys
import importlib.util
from pathlib import Path

block_cipher = None

# Project root
ROOT = os.path.abspath(SPECPATH)

# rawpy ships native dylibs that PyInstaller misses
import rawpy
rawpy_dir = os.path.dirname(rawpy.__file__)
rawpy_binaries = []
for f in os.listdir(rawpy_dir):
    if f.endswith(('.dylib', '.so')) and not f.startswith('_rawpy'):
        src = os.path.join(rawpy_dir, f)
        rawpy_binaries.append((src, 'rawpy'))

dylibs_dir = os.path.join(rawpy_dir, '.dylibs')
if os.path.isdir(dylibs_dir):
    for f in os.listdir(dylibs_dir):
        src = os.path.join(dylibs_dir, f)
        rawpy_binaries.append((src, 'rawpy'))

# Gradio needs its templates, themes, and data files bundled
import gradio
gradio_dir = os.path.dirname(gradio.__file__)


def package_dir(package_name):
    spec = importlib.util.find_spec(package_name)
    if spec is None or spec.origin is None:
        return None
    return os.path.dirname(spec.origin)

datas = []
brands_dir = os.path.join(ROOT, 'Example', 'Brands')
if os.path.isdir(brands_dir):
    datas.append((brands_dir, os.path.join('Example', 'Brands')))

data_candidates = [
    (os.path.join(gradio_dir, 'templates'), 'gradio/templates'),
    (os.path.join(gradio_dir, 'icons'), 'gradio/icons'),
    (os.path.join(gradio_dir, 'themes'), 'gradio/themes'),
    (os.path.join(gradio_dir, 'media_assets'), 'gradio/media_assets'),
    (os.path.join(gradio_dir, 'hash_seed.txt'), 'gradio'),
    (os.path.join(gradio_dir, 'package.json'), 'gradio'),
]

for package_name, files in {
    'safehttpx': [('version.txt', 'safehttpx')],
    'groovy': [('version.txt', 'groovy')],
    'gradio_client': [('types.json', 'gradio_client'), ('package.json', 'gradio_client')],
}.items():
    directory = package_dir(package_name)
    if directory is None:
        continue
    for filename, dest in files:
        data_candidates.append((os.path.join(directory, filename), dest))

for src, dest in data_candidates:
    if os.path.exists(src):
        datas.append((src, dest))

a = Analysis(
    [os.path.join(ROOT, 'webui_launcher.py')],
    pathex=[ROOT],
    binaries=rawpy_binaries,
    datas=datas,
    hiddenimports=[
        'gradio',
        'gradio.themes',
        'caye_watermark.webui',
        'caye_watermark.pipeline',
        'numpy',
        'PIL',
        'rawpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(ROOT, 'runtime_hook.py')],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'notebook',
        'jupyter',
        'PyQt6',
        'PySide6',
        'IPython',
        'sphinx',
        'black',
        'pytest',
        'zmq',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='caye-watermark-web',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='caye-watermark-web',
)
