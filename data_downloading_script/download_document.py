from pathlib import Path
import requests

BASE_DIR = Path("documents")

SOURCES = {
    "01_RBI": [
        {
            "name": "RBI_KYC_Directions.pdf",
            "url": "PASTE_OFFICIAL_PDF_URL_HERE"
        },
        {
            "name": "RBI_Governance_Directions.pdf",
            "url": "PASTE_OFFICIAL_PDF_URL_HERE"
        },
    ],

    "02_IRDAI": [
        {
            "name": "IRDAI_Life_Insurance_Master_Circular.pdf",
            "url": "PASTE_OFFICIAL_PDF_URL_HERE"
        },
    ],

    "03_HDFC_Life": [
        {
            "name": "HDFC_Life_Annual_Report_2024_25.pdf",
            "url": "PASTE_OFFICIAL_PDF_URL_HERE"
        },
    ],

    "04_LIC": [
        {
            "name": "LIC_Annual_Report_2024_25.pdf",
            "url": "PASTE_OFFICIAL_PDF_URL_HERE"
        },
    ],
}


def download_file(url: str, output_path: Path):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/130 Safari/537.36"
        )
    }

    try:
        print(f"Downloading: {output_path.name}")

        response = requests.get(
            url,
            headers=headers,
            timeout=60,
            stream=True
        )

        response.raise_for_status()

        with open(output_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)

        size_mb = output_path.stat().st_size / (1024 * 1024)

        print(f"Downloaded: {output_path}")
        print(f"Size: {size_mb:.2f} MB")
        print("-" * 60)

    except Exception as e:
        print(f"Failed: {url}")
        print(f"Error: {e}")
        print("-" * 60)


def main():

    BASE_DIR.mkdir(exist_ok=True)

    for folder_name, documents in SOURCES.items():

        folder_path = BASE_DIR / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        for document in documents:

            output_path = folder_path / document["name"]

            if output_path.exists():
                print(f"Already exists: {output_path.name}")
                continue

            download_file(
                document["url"],
                output_path
            )


if __name__ == "__main__":
    main()