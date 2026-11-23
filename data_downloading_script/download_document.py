"""Download documents from the standalone app's publisher catalog."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_STORED, ZipFile

import requests

BASE_DIR = Path(__file__).resolve().parent / "downloads"
MIB = 1024 * 1024
MAX_DOCUMENT_BYTES = 128 * MIB
MAX_ARCHIVE_BYTES = 180 * MIB
REQUEST_HEADERS = {
    "User-Agent": "PublicDocumentDownloader/1.0",
    "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.1",
    "Accept-Encoding": "identity",
}


@dataclass(frozen=True)
class Document:
    publisher: str
    title: str
    filename: str
    url: str
    html_marker: bytes = b""

    @property
    def file_type(self) -> str:
        return "HTML" if self.html_marker else "PDF"


HDFC_REPORTS_URL = (
    "https://www.hdfclife.com/content/dam/hdfclifeinsurancecompany/about-us/pdf/"
    "investor-relations/financial-information/annual-reports/"
)
LIC_ARCHIVE_URL = "https://www.licindia.in/documents/20121/92529/"

DOCUMENTS = (
    Document(
        "RBI", "Commercial Banks KYC Directions 2025", "RBI_Commercial_Banks_KYC_Directions_2025.html",
        "https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13141",
        b"know your customer",
    ),
    Document(
        "IRDAI", "Master Circular on Life Insurance Products 2024",
        "IRDAI_Life_Insurance_Master_Circular_2024.pdf",
        "https://irdai.gov.in/documents/37343/991022/%E0%A4%85%E0%A4%82%E0%A4%97%E0%A5%8D%E0%A4%B0%E0%A5%87%E"
        "0%A4%9C%E0%A5%80%2B-%2B%E0%A4%9C%E0%A5%80%E0%A4%B5%E0%A4%A8%2B%E0%A4%AC%E0%A5%80%E0%A4%AE%E0%A4%BE%2"
        "B%E0%A4%89%E0%A4%A4%E0%A5%8D%E0%A4%AA%E0%A4%BE%E0%A4%A6%E0%A5%8B%E0%A4%82%2B%E0%A4%B8%E0%A4%82%E0%A4"
        "%AC%E0%A4%82%E0%A4%A7%E0%A5%80%2B%E0%A4%AE%E0%A4%BE%E0%A4%B8%E0%A5%8D%E0%A4%9F%E0%A4%B0%2B%E0%A4%AA%"
        "E0%A4%B0%E0%A4%BF%E0%A4%AA%E0%A4%A4%E0%A5%8D%E0%A4%B0%2B_%2BMaster%2BCircular%2Bon%2BLife%2BInsuranc"
        "e%2BProducts%2B-%2BEnglish.pdf/56f5b93b-a7c6-30cf-1734-0537e2d8676d?download=true&t=1733233169949&ve"
        "rsion=1.0",
    ),
    Document(
        "HDFC Life", "Integrated Annual Report 2024–25", "HDFC_Life_Annual_Report_2024_25.pdf",
        HDFC_REPORTS_URL + "integrated-annual-report-fy-2024-2025.pdf",
    ),
    Document(
        "LIC", "Annual Report 2024–25", "LIC_Annual_Report_2024_25.pdf",
        "https://web.licindia.in/documents/d/guest/lic_ar-2024-25",
    ),
    Document(
        "RBI", "Periodic Updation of KYC 2025", "RBI_Periodic_Updation_of_KYC_2025.html",
        "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12865",
        b"periodic updation of kyc",
    ),
    Document(
        "HDFC Life", "Integrated Annual Report 2023–24", "HDFC_Life_Annual_Report_2023_24.pdf",
        HDFC_REPORTS_URL + "integrated-annual-report-fy-2023-2024.pdf",
    ),
    Document(
        "HDFC Life", "Integrated Annual Report 2022–23", "HDFC_Life_Annual_Report_2022_23.pdf",
        HDFC_REPORTS_URL + "HDFC-Life-Integrated-Annual-Report-FY2022-23.pdf",
    ),
    Document(
        "LIC", "Annual Report 2023–24", "LIC_Annual_Report_2023_24.pdf",
        LIC_ARCHIVE_URL + "LIC%2Bof%2BIndia_AR_FY%2B2023_24.pdf/6c557500-d9db-bae6-429c-6bb3ca0082d8?t=1722077796687",
    ),
    Document(
        "LIC", "Annual Report 2022–23", "LIC_Annual_Report_2022_23.pdf",
        LIC_ARCHIVE_URL + "LIC-AR-2022-23.pdf/9211aee0-7c0c-f1fb-e4e5-b3a4d951a7b1?t=1691475116093",
    ),
    Document(
        "LIC", "Annual Report 2020–21", "LIC_Annual_Report_2020_21.pdf",
        LIC_ARCHIVE_URL + "2020-21.pdf/171cb4a7-c857-3a65-ad0b-cbaf2bb47680?t=1668579091701",
    ),
)


@dataclass(frozen=True)
class DownloadResult:
    document: Document
    status: str
    size: int = 0
    detail: str = ""


def matches_document(path: Path, document: Document, size: int) -> bool:
    with path.open("rb") as file:
        if document.html_marker:
            head = file.read(256 * 1024).lower()
            return b"<html" in head and document.html_marker in head
        if file.read(5) != b"%PDF-":
            return False
        file.seek(max(0, size - 4096))
        return b"%%EOF" in file.read()


def download_file(
    document: Document,
    client: requests.Session,
    directory: Path = BASE_DIR,
    *,
    replace_existing: bool = False,
) -> DownloadResult:
    destination = directory / document.filename
    temporary = None
    try:
        if not replace_existing and destination.is_file():
            size = destination.stat().st_size
            if matches_document(destination, document, size):
                return DownloadResult(document, "Already saved", size)

        directory.mkdir(parents=True, exist_ok=True)
        with client.get(document.url, headers=REQUEST_HEADERS, timeout=(10, 45), stream=True) as response:
            response.raise_for_status()
            content_length = response.headers.get("Content-Length", "")
            unencoded = response.headers.get("Content-Encoding", "identity").lower() == "identity"
            expected_size = int(content_length) if unencoded and content_length.isdecimal() else None
            if expected_size is not None and expected_size > MAX_DOCUMENT_BYTES:
                raise ValueError(f"File exceeds the {MAX_DOCUMENT_BYTES // MIB} MiB download limit.")

            size = 0
            with NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as file:
                temporary = Path(file.name)
                for chunk in response.iter_content(MIB):
                    size += len(chunk)
                    if size > MAX_DOCUMENT_BYTES:
                        raise ValueError(f"File exceeds the {MAX_DOCUMENT_BYTES // MIB} MiB download limit.")
                    file.write(chunk)

        if expected_size is not None and size != expected_size:
            raise ValueError("The server ended the download before sending the full file.")
        if not matches_document(temporary, document, size):
            raise ValueError(f"The source returned an unexpected or incomplete {document.file_type} document.")

        temporary.replace(destination)
        temporary = None
        return DownloadResult(document, "Downloaded", size)
    except requests.HTTPError as error:
        detail = f"The publisher returned HTTP {error.response.status_code}. Open the source link to check access."
    except requests.Timeout:
        detail = "The publisher took too long to respond. Retry this file."
    except requests.RequestException:
        detail = "The download could not finish. Check your connection or open the source link."
    except (OSError, ValueError) as error:
        detail = str(error)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return DownloadResult(document, "Failed", detail=detail)


def create_archive(results: list[DownloadResult], directory: Path = BASE_DIR) -> bytes:
    files = [directory / result.document.filename for result in results if result.status != "Failed"]
    if sum(file.stat().st_size for file in files) > MAX_ARCHIVE_BYTES:
        raise ValueError(
            f"The files exceed the {MAX_ARCHIVE_BYTES // MIB} MiB browser ZIP limit. "
            "They are available in the local downloads folder."
        )

    with BytesIO() as output:
        with ZipFile(output, "w", compression=ZIP_STORED) as archive:
            for file in files:
                archive.write(file, arcname=file.name)
        return output.getvalue()


def main() -> None:
    with requests.Session() as client:
        for document in DOCUMENTS:
            result = download_file(document, client)
            print(f"{result.status}: {document.filename} {result.detail}".rstrip())


if __name__ == "__main__":
    main()
