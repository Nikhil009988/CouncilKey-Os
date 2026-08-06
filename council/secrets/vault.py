"""Secrets vault - secrets encrypted at rest under COUNCIL_HOME/secrets/.

Backends:
- Fernet (AES) when the `cryptography` package is installed
- HMAC-SHA256 authenticated stream cipher (stdlib-only fallback, marked "xorc")

Master key: $COUNCIL_MASTER_KEY env var, or a generated .master_key file
(chmod 600) beside the vault. Never store plaintext values on disk.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets as _secrets
import threading
import time
from pathlib import Path

VAULT_PATH = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council")) / "secrets" / "vault.json"
_lock = threading.Lock()

try:
    from cryptography.fernet import Fernet  # type: ignore

    _BACKEND = "fernet"
except Exception:  # pragma: no cover - stdlib fallback is the default
    _BACKEND = "xorc"


def _master_key() -> bytes:
    env = os.environ.get("COUNCIL_MASTER_KEY")
    if env:
        return hashlib.scrypt(env.encode("utf-8"), salt=b"councilkey-os-v1", n=2**14, r=8, p=1, dklen=32)
    key_file = VAULT_PATH.parent / ".master_key"
    try:
        if key_file.exists():
            raw = key_file.read_bytes()
            if len(raw) >= 32:
                return raw[:32]
        key = _secrets.token_bytes(32)
        VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key)
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
        return key
    except Exception:
        return hashlib.scrypt(str(time.time()).encode(), salt=b"councilkey-os-v1", n=2**14, r=8, p=1, dklen=32)


def _fernet() -> object | None:
    if _BACKEND == "fernet":
        return Fernet(base64.urlsafe_b64encode(_master_key()))
    return None


def _xorc_stream(key: bytes, iv: bytes, length: int) -> bytes:
    """CTR-like keystream from SHA-256(key || iv || counter)."""
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(key + iv + counter.to_bytes(4, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _encrypt(value: str) -> dict:
    if _BACKEND == "fernet":
        token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
        return {"t": "fernet", "data": token}
    key = _master_key()
    iv = _secrets.token_bytes(16)
    raw = value.encode("utf-8")
    stream = _xorc_stream(key, iv, len(raw))
    ct = bytes(a ^ b for a, b in zip(raw, stream))
    tag = hmac.new(key, iv + ct, hashlib.sha256).hexdigest()
    return {
        "t": "xorc",
        "iv": base64.b64encode(iv).decode("ascii"),
        "ct": base64.b64encode(ct).decode("ascii"),
        "tag": tag,
    }


def _decrypt(enc: dict) -> str:
    if enc.get("t") == "fernet":
        return _fernet().decrypt(enc["data"].encode("ascii")).decode("utf-8")
    key = _master_key()
    iv = base64.b64decode(enc["iv"])
    ct = base64.b64decode(enc["ct"])
    expected = hmac.new(key, iv + ct, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, enc.get("tag", "")):
        raise ValueError("vault integrity check failed")
    stream = _xorc_stream(key, iv, len(ct))
    return bytes(a ^ b for a, b in zip(ct, stream)).decode("utf-8")


def _load() -> dict:
    if VAULT_PATH.exists():
        try:
            data = json.loads(VAULT_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save(data: dict) -> None:
    try:
        VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        VAULT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(VAULT_PATH, 0o600)
        except OSError:
            pass
    except Exception as exc:
        raise RuntimeError(f"cannot write the secrets vault at {VAULT_PATH}: {exc}") from exc


def set_secret(key: str, value: str) -> dict:
    """Store an encrypted secret. Key: [A-Za-z0-9_.-]{1,64}."""
    if not key or not re.fullmatch(r"[A-Za-z0-9_.\-]+", key) or len(key) > 64:
        return {"ok": False, "error": "invalid key (use letters, digits, . _ -)"}
    if value is None or len(value) > 8000:
        return {"ok": False, "error": "value too long (max 8000 chars)"}
    with _lock:
        data = _load()
        data[key] = {"enc": _encrypt(str(value)), "updated": time.time()}
        try:
            _save(data)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    return {"ok": True, "key": key}


def get_secret(key: str) -> str | None:
    """Decrypt and return a secret value (used by agents internally only)."""
    with _lock:
        data = _load()
        enc = data.get(key)
        if not enc:
            return None
        try:
            return _decrypt(enc["enc"])
        except Exception:
            return None


def list_secrets() -> dict:
    with _lock:
        data = _load()
    keys = sorted(data.keys())
    return {
        "ok": True,
        "keys": keys,
        "count": len(keys),
        "backend": _BACKEND,
        "path": str(VAULT_PATH),
    }


def mask_secret(key: str) -> dict:
    value = get_secret(key)
    if value is None:
        return {"ok": False, "exists": False}
    if len(value) < 5:
        masked = "*" * len(value)
    else:
        masked = value[:2] + "*" * (len(value) - 4) + value[-2:]
    return {"ok": True, "exists": True, "key": key, "masked": masked, "length": len(value)}


def delete_secret(key: str) -> dict:
    with _lock:
        data = _load()
        if key not in data:
            return {"ok": False, "error": "secret not found"}
        del data[key]
        _save(data)
    return {"ok": True, "key": key}


def vault_status() -> dict:
    with _lock:
        data = _load()
    return {
        "ok": True,
        "backend": _BACKEND,
        "entries": len(data),
        "path": str(VAULT_PATH),
        "master_key": "env" if os.environ.get("COUNCIL_MASTER_KEY") else "keyfile",
    }
