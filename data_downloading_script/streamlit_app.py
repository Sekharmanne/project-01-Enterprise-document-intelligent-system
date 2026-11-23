"""Standalone Streamlit interface for downloading public documents."""

import csv
from io import StringIO

import requests
import streamlit as st

from download_document import BASE_DIR, DOCUMENTS, MIB, Document, DownloadResult, create_archive, download_file


def run_batch(documents: list[Document], replace_existing: bool) -> list[DownloadResult]:
    progress = st.progress(0, text=f"Preparing {len(documents)} documents")
    results = []
    with requests.Session() as client:
        for index, document in enumerate(documents, start=1):
            progress.progress(
                (index - 1) / len(documents),
                text=f"Checking {index} of {len(documents)} · {document.publisher} {document.title}",
            )
            results.append(download_file(document, client, BASE_DIR, replace_existing=replace_existing))
    progress.progress(1.0, text=f"Checked all {len(documents)} documents")
    return results


def result_table(results: list[DownloadResult]) -> list[dict]:
    return [
        {
            "Publisher": result.document.publisher,
            "File": result.document.filename,
            "Status": result.status,
            "Size (MiB)": round(result.size / MIB, 2) if result.status != "Failed" else None,
            "Details": result.detail,
            "Source": result.document.url,
        }
        for result in results
    ]


def show_results() -> None:
    results = st.session_state.get("results", [])
    if not results:
        return

    failed = [result.document for result in results if result.status == "Failed"]
    if failed and st.button("Retry failed files", key="retry"):
        updated = {
            result.document.filename: result
            for result in run_batch(failed, st.session_state["replace_existing"])
        }
        results = [updated.get(result.document.filename, result) for result in results]
        st.session_state["results"] = results
        st.session_state.pop("archive", None)

    st.subheader("Download results")
    columns = st.columns(3)
    for column, status in zip(columns, ("Downloaded", "Already saved", "Failed")):
        column.metric(status, sum(result.status == status for result in results))

    rows = result_table(results)
    st.dataframe(
        rows,
        hide_index=True,
        column_config={"Source": st.column_config.LinkColumn("Source", display_text="Open source")},
    )

    report = StringIO()
    writer = csv.DictWriter(report, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

    archive_col, report_col = st.columns(2)
    if any(result.status != "Failed" for result in results):
        with archive_col:
            if "archive" not in st.session_state and st.button("Prepare ZIP", key="prepare_archive"):
                try:
                    st.session_state["archive"] = create_archive(results, BASE_DIR)
                except (OSError, ValueError) as error:
                    st.error(str(error))
            if "archive" in st.session_state:
                st.download_button(
                    "Download ZIP", st.session_state["archive"],
                    file_name="documents.zip", mime="application/zip", key="download_archive",
                )
    report_col.download_button(
        "Download CSV report", report.getvalue(),
        file_name="download-report.csv", mime="text/csv", key="download_report",
    )


def main() -> None:
    st.set_page_config(page_title="Document Downloader", layout="wide")
    st.title("Document downloader")
    st.caption("Download public circulars, directions, and annual reports from their official publishers.")

    publisher_col, document_col = st.columns(2)
    publishers = publisher_col.multiselect(
        "Publishers", sorted({document.publisher for document in DOCUMENTS}),
        placeholder="All publishers", key="publishers",
    )
    available = [document for document in DOCUMENTS if not publishers or document.publisher in publishers]
    selected = document_col.multiselect(
        "Specific documents (optional)", available,
        format_func=lambda document: f"{document.publisher} · {document.title}",
        placeholder="All documents from selected publishers", key="documents",
    )
    candidates = selected or available

    count_col, options_col = st.columns(2, vertical_alignment="bottom")
    count = count_col.number_input(
        "How many documents do you want to download?",
        min_value=1, max_value=len(candidates), value=min(4, len(candidates)), step=1,
        key=f"count_{len(candidates)}",
    )
    replace_existing = options_col.checkbox("Redownload files already saved", key="redownload")
    queue = candidates[:count]

    with st.expander(f"Download queue ({len(queue)})", expanded=True):
        st.dataframe(
            [
                {"Publisher": document.publisher, "Document": document.title,
                 "Format": document.file_type, "Source": document.url}
                for document in queue
            ],
            hide_index=True,
            column_config={"Source": st.column_config.LinkColumn("Official source", display_text="Open source")},
        )

    st.caption("Files are saved in this app’s `downloads/` folder.")
    if st.button(f"Download {count} {'document' if count == 1 else 'documents'}", type="primary", key="run"):
        st.session_state["results"] = run_batch(queue, replace_existing)
        st.session_state["replace_existing"] = replace_existing
        st.session_state.pop("archive", None)

    show_results()


if __name__ == "__main__":
    main()
