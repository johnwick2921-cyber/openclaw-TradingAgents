import os

from fastapi import APIRouter

router = APIRouter(prefix="/api")

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_CACHE_DIR = os.path.join(_PROJECT_ROOT, "tradingagents", "dataflows", "data_cache")


def _format_size(size_bytes: int) -> str:
    """Return a human-readable file size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


def _dir_size(path: str) -> int:
    """Calculate total size of all files in a directory tree (bytes)."""
    total = 0
    if not os.path.isdir(path):
        return 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for fname in filenames:
            fp = os.path.join(dirpath, fname)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


@router.get("/cache/size")
async def get_cache_size() -> dict:
    """Return the total size of the data cache directory."""
    size = _dir_size(_CACHE_DIR)
    return {"size_bytes": size, "size_human": _format_size(size)}


@router.delete("/cache")
async def clear_cache() -> dict:
    """Delete all files in the data cache directory."""
    if not os.path.isdir(_CACHE_DIR):
        return {"deleted_files": 0}

    deleted = 0
    for dirpath, dirnames, filenames in os.walk(_CACHE_DIR, topdown=False):
        for fname in filenames:
            fp = os.path.join(dirpath, fname)
            try:
                os.remove(fp)
                deleted += 1
            except OSError:
                pass
        # Remove empty subdirectories but keep the cache root
        if dirpath != _CACHE_DIR:
            try:
                os.rmdir(dirpath)
            except OSError:
                pass

    return {"deleted_files": deleted}
