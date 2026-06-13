"""CI yardımcı: bir log dosyasının son satırlarını tek bir GitHub 'error' annotation'ı
olarak yayar (public repo'da API'den auth'suz okunabilir → uzaktan teşhis).

Kullanım: python scripts/ci_annotate.py [dosya]   (varsayılan: pytest-output.txt)
"""
import pathlib
import sys

target = sys.argv[1] if len(sys.argv) > 1 else "pytest-output.txt"
path = pathlib.Path(target)
text = path.read_text(errors="replace") if path.exists() else f"({target} bulunamadi)"
tail = "\n".join(text.splitlines()[-250:]) or "(cikti bos)"

# GitHub workflow komutunda yeni satırlar %0A olarak kodlanmalı
enc = tail.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
print(f"::error title={path.name}::{enc}")
