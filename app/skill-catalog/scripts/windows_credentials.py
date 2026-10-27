"""Windows-only credential storage. No command-line secret interface or logging."""
import ctypes
from ctypes import wintypes
import os

MESHY_TARGET = "Codex/Services/Meshy/APIKey"


class CredentialError(RuntimeError):
    pass


class Credential(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]


def _api():
    if os.name != "nt":
        raise CredentialError("Хранилище ключа доступно только в Windows.")
    api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
    api.CredWriteW.restype = wintypes.BOOL
    api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(Credential))]
    api.CredReadW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    api.CredFree.restype = None
    api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    api.CredDeleteW.restype = wintypes.BOOL
    return api


def read(target=MESHY_TARGET, presence_only=False):
    api = _api()
    ptr = ctypes.POINTER(Credential)()
    if not api.CredReadW(target, 1, 0, ctypes.byref(ptr)):
        if ctypes.get_last_error() == 1168:
            return False if presence_only else None
        raise CredentialError("Windows не предоставила доступ к хранилищу ключа.")
    try:
        return True if presence_only else ctypes.string_at(ptr.contents.CredentialBlob, ptr.contents.CredentialBlobSize).decode("utf-8")
    finally:
        api.CredFree(ptr)


def write(secret, target=MESHY_TARGET):
    raw = secret.encode("utf-8")
    if not 0 < len(raw) <= 2560:
        raise CredentialError("Неверная длина ключа.")
    api = _api()
    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    credential = Credential(Type=1, TargetName=target, Comment="Meshy API key for local Codex integration", CredentialBlobSize=len(raw), CredentialBlob=buffer, Persist=2, UserName="Meshy API")
    try:
        if not api.CredWriteW(ctypes.byref(credential), 0):
            raise CredentialError("Windows не сохранила ключ. Прежняя запись не удалялась.")
        if read(target) != secret:
            raise CredentialError("Не удалось подтвердить сохранение ключа.")
    finally:
        ctypes.memset(buffer, 0, len(raw))


def delete_test_credential(target):
    if not target.startswith(MESHY_TARGET + "/test/"):
        raise ValueError("Only test credentials may be removed by this helper")
    api = _api()
    if not api.CredDeleteW(target, 1, 0) and ctypes.get_last_error() != 1168:
        raise CredentialError("Windows не удалила тестовую запись.")


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def protect(raw, decrypt=False):
    """DPAPI current-user encryption for a config backup containing an old key."""
    if os.name != "nt":
        raise CredentialError("DPAPI требует Windows.")
    crypto = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
    kernel = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    data = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    source, output = Blob(len(raw), data), Blob()
    if decrypt:
        fn = crypto.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        description = None
    else:
        fn = crypto.CryptProtectData
        fn.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        description = "Codex Meshy configuration backup"
    fn.restype = wintypes.BOOL
    try:
        if not fn(ctypes.byref(source), description, None, None, None, 1, ctypes.byref(output)):
            raise CredentialError("Windows не обработала защищённую резервную копию.")
        return ctypes.string_at(output.data, output.size)
    finally:
        ctypes.memset(data, 0, len(raw))
        if output.data:
            kernel.LocalFree(output.data)
