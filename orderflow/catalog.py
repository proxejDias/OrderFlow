"""Validated catalog JSON persistence with atomic replacement."""
import json
import os
import tempfile
from pathlib import Path
from .core import Product


def _validate(products):
    products = list(products)
    if any(not isinstance(p, Product) for p in products):
        raise ValueError("Catalog must contain Products")
    if len({p.id for p in products}) != len(products):
        raise ValueError("Duplicate product ID")
    return products


def save_products(products, path):
    products = _validate(products)
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as stream:
            temporary = stream.name
            json.dump([p.to_dict() for p in products], stream, ensure_ascii=False, indent=2,
                      allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def load_products(path):
    with open(path, encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, list):
        raise ValueError("Catalog JSON must be a list")
    return _validate(Product.from_dict(item) for item in data)
