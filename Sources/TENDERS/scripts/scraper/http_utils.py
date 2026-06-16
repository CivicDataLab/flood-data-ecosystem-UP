
import os, json, requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing, threading
from collections import defaultdict



VIEW_MORE_BASE = "https://etender.up.nic.in/nicgep/app?component=view&page=WebTenderStatusLists&service=direct&session=T&sp="
VIEW_MORE_BASE_URL = "https://etender.up.nic.in/nicgep/app?component=$DirectLink&page=WebTenderStatus&service=direct&session=T&sp="
STAGE_SUMMARY_BASE = "https://etender.up.nic.in/nicgep/app?component=$DirectLink_0&page=WebTenderStatus&service=direct&session=T&sp="

SP_TOKEN_FILE = r"C:\Users\cdl\Desktop\Scrapper\assam-tenders-data\code\scraper\scraped_recent_tenders\sp_tokens.json"
OUTPUT_DIR = r"D:\CDL\saved-html\2024\test-output"
COOKIE_FILE = r"C:\Users\cdl\Desktop\Scrapper\assam-tenders-data\code\scraper\scraped_recent_tenders\cookies.json"
VIEW_MORE_SP_JSON_FILE = r"C:\Users\cdl\Desktop\Scrapper\assam-tenders-data\code\scraper\scraped_recent_tenders\details_page_sptokens.json"



shared_sp_tokens = defaultdict(dict)
shared_lock = threading.Lock()


def load_cookies_as_dict(cookie_file):
    with open(cookie_file, "r") as f:
        cookies = json.load(f)
    return {cookie['name']: cookie['value'] for cookie in cookies}


def extract_and_store_sp_token(html_file_path, tender_id, page):
    with open(html_file_path, 'r', encoding='utf-8') as html_file:
        soup = BeautifulSoup(html_file, 'html.parser')
    view_more_link = soup.find('a', id='DirectLink')
    if view_more_link:
        sp_token = view_more_link['href'].split('sp=')[-1]
        with shared_lock:
            shared_sp_tokens[page][tender_id] = sp_token
    else:
        print(f"[{tender_id}] View More link not found")


def fetch_and_save_tender_pages(page, tender_id, sp_token, cookies_dict):
    session = requests.Session()
    session.cookies.update(cookies_dict)

    # Optional but helps with intermediary caching/proxies
    session.headers.update({
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": "Mozilla/5.0",
    })

    try:
        page_folder = os.path.join(OUTPUT_DIR, page)
        os.makedirs(page_folder, exist_ok=True)

        # 1) FIRST hit view page to bind session to this tender
        view_url = VIEW_MORE_BASE + sp_token
        view_resp = session.post(view_url, timeout=30)

        # 2) THEN fetch summary (now session is on the correct tender)
        summary_url = STAGE_SUMMARY_BASE + sp_token
        summary_resp = session.post(summary_url, timeout=30)
        with open(os.path.join(page_folder, f"{tender_id}_summary.html"), "w", encoding="utf-8") as f:
            f.write(summary_resp.text)

        # 3) Extract view_details sp_token from view.html content (use view_resp, not a re-request)
        soup = BeautifulSoup(view_resp.text, "html.parser")
        view_more_link = soup.find("a", id="DirectLink")
        if not view_more_link:
            print(f"[{tender_id}] View More link not found")
            return
        view_details_sp_token = view_more_link["href"].split("sp=")[-1]

        with shared_lock:
            shared_sp_tokens[page][tender_id] = view_details_sp_token

        # 4) Save view_details.html
        view_details_url = VIEW_MORE_BASE_URL + view_details_sp_token
        details_resp = session.post(view_details_url, timeout=30)
        with open(os.path.join(page_folder, f"{tender_id}_view_details.html"), "w", encoding="utf-8") as f:
            f.write(details_resp.text)

    except Exception as e:
        print(f"{tender_id} failed: {e}")



# def fetch_and_save_tender_pages(page, tender_id, sp_token, cookies_dict):
#     session = requests.Session()
#     session.cookies.update(cookies_dict)

#     try:
#         page_folder = os.path.join(OUTPUT_DIR, page)
#         os.makedirs(page_folder, exist_ok=True)

#         # _view.html
#         view_url = VIEW_MORE_BASE + sp_token
#         view_path = os.path.join(page_folder, f"{tender_id}_view.html")
#         response = session.post(view_url, timeout=30)
#         with open(view_path, "w", encoding="utf-8") as f:
#             f.write(response.text)

#         extract_and_store_sp_token(view_path, tender_id, page)
        

#         # _summary.html
#         summary_url = STAGE_SUMMARY_BASE + sp_token
#         response = session.post(summary_url, timeout=30)
#         with open(os.path.join(page_folder, f"{tender_id}_summary.html"), "w", encoding="utf-8") as f:
#             f.write(response.text)

#     except Exception as e:
#         print(f"{tender_id} failed: {e}")


def save_html_responses(sp_data):

    cookies_dict = load_cookies_as_dict(COOKIE_FILE)

    tasks = []
    with ThreadPoolExecutor(max_workers=1) as exe:
        for page, tenders in sp_data.items():
            for tender_id, sp_token in tenders.items():
                tasks.append(exe.submit(
                    fetch_and_save_tender_pages,
                    page, tender_id, sp_token, cookies_dict
                ))
            
        for fut in as_completed(tasks):
            _ = fut.result()

    with open(VIEW_MORE_SP_JSON_FILE, "w") as f:
        json.dump(shared_sp_tokens, f, indent=4)


# def save_view_more_html_responses(sp_data):
#     cookies_dict = load_cookies_as_dict(COOKIE_FILE)

#     def fetch_view_detail(page, tender_id, sp_token):
#         try:
#             session = requests.Session()
#             session.cookies.update(cookies_dict)
#             view_details_url = VIEW_MORE_BASE_URL + sp_token
#             page_folder = os.path.join(OUTPUT_DIR, page)
#             os.makedirs(page_folder, exist_ok=True)
#             response = session.post(view_details_url, timeout=30)
#             view_path = os.path.join(page_folder, f"{tender_id}_view_details.html")
#             with open(view_path, "w", encoding="utf-8") as f:
#                 f.write(response.text)
#         except Exception as e:
#             print(f"{tender_id} view_details failed: {e}")

#     with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count() * 4) as exe:
#         futures = [
#             exe.submit(fetch_view_detail, page, tender_id, sp_token)
#             for page, tenders in sp_data.items()
#             for tender_id, sp_token in tenders.items()
#         ]
#         for fut in as_completed(futures):
#             _ = fut.result()


if __name__ == "__main__":
    # Load the SP tokens from JSON (instead of empty shared_sp_tokens)
    with open(SP_TOKEN_FILE, "r") as f:
        sp_data = json.load(f)

    # # Now process
    save_html_responses(sp_data)

    # Use the extracted tokens for view details
    # save_view_more_html_responses(shared_sp_tokens)

    # Save the new tokens for reuse
    # with open(VIEW_MORE_SP_JSON_FILE, "w") as f:
    #     json.dump(shared_sp_tokens, f, indent=4)



