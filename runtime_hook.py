"""PyInstaller runtime hook: patch Gradio for frozen bundles.

Gradio's component metaclass reads its own .py source files at import
time to generate .pyi stubs. This fails in PyInstaller bundles because
source files live inside the PYZ archive, not on disk.

We intercept the import of gradio.component_meta and replace
create_or_modify_pyi with a no-op before any metaclass calls it.
"""
import os
import sys

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

if getattr(sys, "frozen", False):
    _original_import = __builtins__.__import__
    _patched = False

    def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        global _patched
        mod = _original_import(name, globals, locals, fromlist, level)
        if not _patched and name == "gradio.component_meta":
            mod.create_or_modify_pyi = lambda *a, **kw: None
            _patched = True
        return mod

    __builtins__.__import__ = _guarded_import
