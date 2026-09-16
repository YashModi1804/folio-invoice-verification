"""Download public Microsoft evaluation samples into ignored local storage."""

import hashlib
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "data/demo-pack/public"
SOURCES = {
    "azure-contoso-invoice.pdf": "https://raw.githubusercontent.com/Azure-Samples/azure-ai-content-understanding-assets/main/document/invoice.pdf",
    "azure-invoice-1.pdf": "https://raw.githubusercontent.com/Azure/azure-sdk-for-python/master/sdk/formrecognizer/azure-ai-formrecognizer/samples/sample_forms/forms/Invoice_1.pdf",
    "azure-british-invoice.png": "https://raw.githubusercontent.com/Azure-Samples/document-intelligence-code-samples/main/Data/invoice/invoice-english-britain.png",
    "azure-invoice-6.pdf": "https://raw.githubusercontent.com/Azure-Samples/document-intelligence-code-samples/main/Data/invoice/Invoice-6.pdf",
    "AZURE-SAMPLES-LICENSE.md": "https://raw.githubusercontent.com/Azure-Samples/document-intelligence-code-samples/main/LICENSE.md",
    "AZURE-SDK-LICENSE.txt": "https://raw.githubusercontent.com/Azure/azure-sdk-for-python/main/LICENSE",
    "AZURE-CONTENT-LICENSE.md": "https://raw.githubusercontent.com/Azure-Samples/azure-ai-content-understanding-assets/main/LICENSE.md",
}


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    manifest = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for name, url in SOURCES.items():
            path = DESTINATION / name
            if not path.exists():
                response = client.get(url)
                response.raise_for_status()
                path.write_bytes(response.content)
            manifest.append(
                {
                    "file": name,
                    "source": url,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    (DESTINATION / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Prepared {len(manifest)} source and license files in {DESTINATION}")


if __name__ == "__main__":
    main()
