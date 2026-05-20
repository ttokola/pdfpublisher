import requests
from datetime import datetime, timezone
from typing import Set, Iterable, List, Tuple, Dict
from pypdf import PdfReader


def find_links(file: str) -> List[Dict]:
    """Extract link annotations from a PDF.

    Args:
        file: Path to the PDF file.

    Returns:
        A list of dicts, each with keys:
        - "url" (str): the URI string found in the annotation
        - "file" (str): the source PDF filename passed in
        - "page_number" (int): 1-based page index where the link was found
    """
    reader = PdfReader(file)
    key = '/Annots'
    uri = '/URI'
    ank = '/A'
    links = []

    for page_index, page in enumerate(reader.pages):
        annotations = page.get(key)
        if not annotations:
            continue
        for annot in annotations:
            try:
                u = annot.get_object()
            except Exception as e:
                print(f"Error getting annotation object on page {page_index}: {e}")
                continue
            if ank in u and uri in u[ank]:
                url = u[ank][uri]
                links.append({"url": url, "file": file, "page_number": page_index + 1, "error_code": None})
    return links


def test_link(links: Iterable[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Check HTTP status for each link dict.

    Args:
        links: Iterable of dicts like {"url": str, "file": str, "page_number": int}.

    Returns:
        Tuple(dead_links, alive_links) where each element is a list of the
        original dicts that were determined dead or alive, respectively.
    """
    seen: Set[Tuple[str, str, int]] = set()
    dead_links: List[Dict] = []
    alive_links: List[Dict] = []

    for item in links:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not url:
            continue
        key = (url, item.get("file"), item.get("page_number"))
        if key in seen:
            continue
        seen.add(key)
        try:
            resp = requests.get(url, allow_redirects=True, timeout=5, auth=None, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code >= 500 or resp.status_code == 404:
                item.update({"error_code": resp.status_code})
                dead_links.append(item)
            elif resp.status_code >= 400:
                item.update({"error_code": resp.status_code})
                continue
            else:
                alive_links.append(item)
        except requests.RequestException:
            item.update({"error_code": "timeout"})
            dead_links.append(item)

    return dead_links, alive_links

def add_dead_links_to_db(cursor, file, dead_links):

    check_time = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
    rows = []

    for item in dead_links:
        url = item.get("url")
        if not url:
            continue
        page = item.get("page_number")
        error_code = item.get("error_code")
        rows.append((error_code, file, url, page, check_time))

    if rows:
        cursor.executemany(
            "INSERT INTO dead_links (error_code, file, url, page_number, checked_at) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        cursor.connection.commit()

def run_health_check(file: str):
    links = find_links(file)
    dead, alive = test_link(links)
    return dead, alive
