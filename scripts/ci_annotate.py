"""CI yardımcı: pytest çıktısının son satırlarını tek bir GitHub 'error' annotation'ı
olarak yayar.

Public repo'da annotation'lar GitHub API'den kimlik doğrulaması olmadan okunabildiği
için, CI hataları uzaktan (gh/yetki olmadan) teşhis edilebilir.
"""
import pathlib

path = pathlib.Path("pytest-output.txt")
text = path.read_text(errors="replace") if path.exists() else "(pytest-output.txt bulunamadi)"
tail = "\n".join(text.splitlines()[-250:]) or "(cikti bos)"

# GitHub workflow komutunda yeni satırlar %0A olarak kodlanmalı
enc = tail.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
print(f"::error title=pytest::{enc}")
