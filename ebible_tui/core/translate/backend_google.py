from __future__ import annotations

import asyncio
import os
import shutil

from ebible_tui.core.translate.backend_base import TranslatorBackend

_SUPPORTED = {'am', 'en'}


class TranslationError(RuntimeError):
    pass


def _resolve_trans_cmd() -> str:
    # Allow override; default to 'trans' from PATH
    return os.environ.get('EBIBLE_GOOGLE_TRANS_CMD') or 'trans'


async def _run_google(text: str, src: str, tgt: str, timeout_sec: float = 30.0) -> str:
    if src not in _SUPPORTED or tgt not in _SUPPORTED:
        raise TranslationError(f'unsupported language pair: {src}->{tgt}')
    cmd = _resolve_trans_cmd()
    exe = cmd.split()[0]
    if shutil.which(exe) is None:
        raise TranslationError(f'command not found: {exe} (install translate-shell)')
    proc = await asyncio.create_subprocess_exec(
        cmd,
        '-b',
        '-e',
        'google',
        f'{src}:{tgt}',
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdin is not None and proc.stdout is not None
    try:
        proc.stdin.write(text.encode('utf-8'))
        await proc.stdin.drain()
        proc.stdin.close()
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
    except TimeoutError:
        proc.kill()
        raise TranslationError('translation timed out') from None
    if proc.returncode != 0:
        msg = (stderr or b'').decode('utf-8', errors='replace').strip()
        raise TranslationError(f'translator failed (code {proc.returncode}): {msg}')
    return stdout.decode('utf-8', errors='replace').strip()


class GoogleBackend(TranslatorBackend):
    def translate(self, text: str, src: str, tgt: str, timeout_sec: float = 30.0) -> str:
        return asyncio.run(_run_google(text, src, tgt, timeout_sec))

    async def translate_async(
        self, text: str, src: str, tgt: str, timeout_sec: float = 30.0
    ) -> str:
        return await _run_google(text, src, tgt, timeout_sec)
