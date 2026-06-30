# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CAYE Watermark WebUI.

Build with:
    pyinstaller caye-watermark-web.spec

Or use the Makefile:
    make build
"""
import os
import sys
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
import safehttpx
safehttpx_dir = os.path.dirname(safehttpx.__file__)
import gradio_client
gradio_client_dir = os.path.dirname(gradio_client.__file__)
import groovy
groovy_dir = os.path.dirname(groovy.__file__)

datas = []
for src, dest in [
    (os.path.join(gradio_dir, 'templates'), 'gradio/templates'),
    (os.path.join(gradio_dir, 'icons'), 'gradio/icons'),
    (os.path.join(gradio_dir, 'themes'), 'gradio/themes'),
    (os.path.join(gradio_dir, 'media_assets'), 'gradio/media_assets'),
    (os.path.join(gradio_dir, 'hash_seed.txt'), 'gradio'),
    (os.path.join(gradio_dir, 'package.json'), 'gradio'),
    (os.path.join(safehttpx_dir, 'version.txt'), 'safehttpx'),
    (os.path.join(groovy_dir, 'version.txt'), 'groovy'),
    (os.path.join(gradio_client_dir, 'types.json'), 'gradio_client'),
    (os.path.join(gradio_client_dir, 'package.json'), 'gradio_client'),
]:
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
