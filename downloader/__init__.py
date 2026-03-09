"""
PhotoPrism downloader package for fetching and managing photos from a PhotoPrism instance.
"""

__all__ = ["PhotoPrismAPI"]


def __getattr__(name):
    """Lazy-import PhotoPrismAPI so importing downloader.auth does not load main (pandas)."""
    if name == "PhotoPrismAPI":
        from .main import PhotoPrismAPI

        return PhotoPrismAPI
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
