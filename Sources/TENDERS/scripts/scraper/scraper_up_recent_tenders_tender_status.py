from selenium.webdriver.support.wait import WebDriverWait
import time
import os
import warnings
import json
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
from pathlib import Path

from Utils import SeleniumScrappingUtils
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
import http_utils
import extract_tender

warnings.filterwarnings("ignore", category=DeprecationWarning)


# Config (edit if needed)

URL = "https://etender.up.nic.in/nicgep/app?page=WebTenderStatusLists&service=page"
TENDER_STATUS_VALUE = "6"  # current script uses "6"

# Where to store outputs (relative to repo/run location)
CWD = Path.cwd()
SCRAPER_STATE_DIR = CWD / "Sources" / "TENDERS" / "scripts" / "scraper" / "scraped_recent_tenders"
SCRAPER_STATE_DIR.mkdir(parents=True, exist_ok=True)

SP_TOKENS_PATH = SCRAPER_STATE_DIR / "sp_tokens.json"
COOKIES_PATH = SCRAPER_STATE_DIR / "cookies.json"

# HTML output root (each page becomes a folder under this)
HTML_OUTPUT_DIR = SCRAPER_STATE_DIR / "saved_html"
HTML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Where to write extracted CSVs from saved HTML
EXTRACTED_OUT_DIR = SCRAPER_STATE_DIR / "extracted_csvs"
EXTRACTED_OUT_DIR.mkdir(parents=True, exist_ok=True)

# Where to write view-details SP tokens extracted by http_utils
VIEW_MORE_SP_JSON_PATH = SCRAPER_STATE_DIR / "details_page_sptokens.json"



# Selenium driver setup

chromedriver_path = ""  # keep as your existing approach, empty means default path

chrome_options = Options()
# chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.page_load_strategy = "eager"
chrome_options.add_argument("--start-maximized")

chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-infobars")
chrome_options.add_argument("--disable-notifications")
chrome_options.add_argument("--disable-cloud-import")
chrome_options.add_argument("--disable-sync")
chrome_options.add_argument("--disable-client-side-phishing-detection")
chrome_options.add_argument("--disable-background-networking")
chrome_options.add_argument("--disable-background-timer-throttling")
chrome_options.add_argument("--disable-backgrounding-occluded-windows")
chrome_options.add_argument("--disable-component-update")
chrome_options.add_argument("--disable-default-apps")
chrome_options.add_argument("--log-level=3")

chrome_service = Service(chromedriver_path)
driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
driver.get(URL)

# Keep your table-type mapping
dict_tables_type = {
    "Bids List": "Vertical",
    "Technical Bid Opening Summary": "Horizontal",
    "Technical Evaluation Summary Details": "Horizontal",
    "Bid Opening Summary": "Horizontal",
    "Finance Bid Opening Summary": "Horizontal",
    "Financial Evaluation Bid List": "Vertical",
    "Finance Evaluation Summary Details": "Horizontal",
    "AOC": "Horizontal",
    "Awarded Bids List": "Vertical",
    "Tender Revocation List": "Vertical",
    "Corrigendum Details": "Vertical",
}


# Captcha helper

try:
    from captcha import captcha_ocr  # type: ignore
    _solve_captcha = lambda: captcha_ocr()
except Exception:
    from captcha import captcha  # type: ignore
    _solve_captcha = lambda: captcha(driver, '//*[@id="captchaImage"]')


def captcha_input(driver, xpath_image, xpath_input_text, reload_button_xpath=None, max_attempts=12):
    invalid_xpath = '//*[@id="If_19"]/table/tbody/tr/td/span/b'
    search_xpath = '//*[@id="Search"]'

    if reload_button_xpath is None:
        reload_button_xpath = "/html/body/div[1]/table/tbody/tr[2]/td/table/tbody/tr/td[2]/form/table/tbody/tr/td/table/tbody/tr/td/table/tbody/tr/td/table/tbody/tr[4]/td/table/tbody/tr/td/table/tbody/tr[19]/td/table/tbody/tr/td[3]/button"

    for attempt in range(1, max_attempts + 1):
        captcha_element = driver.find_element(By.XPATH, xpath_image)
        SeleniumScrappingUtils.save_image_as_png(captcha_element)

        text = _solve_captcha()

        captcha_input_element = SeleniumScrappingUtils.get_page_element(driver, xpath_input_text)
        captcha_input_element.clear()
        SeleniumScrappingUtils.input_text_box(driver, captcha_input_element, text)

        driver.find_element(By.XPATH, search_xpath).click()
        time.sleep(2)
        driver.refresh()
        time.sleep(2)
        if not driver.find_elements(By.XPATH, invalid_xpath):
            return True

        print(f"[captcha] attempt {attempt} failed, reloading...")
        driver.find_element(By.XPATH, reload_button_xpath).click()
        time.sleep(1.5)

    raise RuntimeError(f"CAPTCHA failed after {max_attempts} attempts")

SeleniumScrappingUtils.select_drop_down(driver, '//*[@id="tenderStatus"]', TENDER_STATUS_VALUE)


def set_readonly_date(driver, input_id: str, date_str: str, timeout: int = 20):
    """
    Sets a Tapestry DatePicker input (often readonly) to date_str (dd/MM/yyyy),
    and dispatches events so any JS listeners/validators update.
    """
    el = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.ID, input_id))
    )

    driver.execute_script(
        """
        const el = arguments[0];
        const v  = arguments[1];

        // Ensure value can be assigned even if readonly is enforced in JS.
        // We temporarily remove readonly attribute, set value, then restore.
        const wasReadonly = el.hasAttribute('readonly');
        if (wasReadonly) el.removeAttribute('readonly');

        el.focus();
        el.value = v;

        el.dispatchEvent(new Event('input',  { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('blur',   { bubbles: true }));

        if (wasReadonly) el.setAttribute('readonly', 'readonly');
        """,
        el,
        date_str
    )

input_from_date = input("Enter From Date (DD/MM/YYYY): ")
input_to_date = input("Enter To Date (DD/MM/YYYY): ")

set_readonly_date(driver, "fromDate", input_from_date)
set_readonly_date(driver, "toDate",   input_to_date)   # assuming there is an input with id="toDate"


time.sleep(0.5)


from_date_input = driver.find_element(By.XPATH, '//*[@id="fromDate"]')
to_date_input = driver.find_element(By.XPATH, '//*[@id="toDate"]')




# from_date_input.send_keys(from_date)
# to_date_input.send_keys(to_date)

# Token extraction

def get_table_links(driver, table_xpath):
    table = SeleniumScrappingUtils.get_page_element(driver, table_xpath)
    elements_list = table.find_elements(By.CSS_SELECTOR, "a")
    links = [element.get_attribute("href") for element in elements_list]
    rows = table.find_elements(By.CSS_SELECTOR, "tr")
    tender_ids = [row.find_element("xpath", "td[2]").text for row in rows[1:-2]]

    next_page_elements = table.find_elements("xpath", '//*[@id="loadNext"]')
    next_page_link = next_page_elements[0].get_attribute("href") if next_page_elements else None
    return table, links, next_page_link, tender_ids


def extract_sp_tokens_paginated(
    driver,
    output_file: Path,
    cookies_file: Path,
):

    page_count = 1
    all_data = {}

    def extract_tokens_from_page():
        table, links, _, tender_ids = get_table_links(driver, '//*[@id="tabList"]')
        page_dict = {}

        def process_link(tid_link_pair):
            tender_id, link = tid_link_pair
            parsed_url = urlparse(link)
            query_params = parse_qs(parsed_url.query)
            sp_token = query_params.get("sp", [""])[0]
            return tender_id, sp_token

        # Keep your parallelism style
        with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count() * 4) as executor:
            results = executor.map(process_link, zip(tender_ids, links))
            for tid, token in results:
                if tid and token:
                    page_dict[tid] = token

        return page_dict

    while True:
        # Save cookies so http_utils can reuse them
        with open(cookies_file, "w", encoding="utf-8") as f:
            json.dump(driver.get_cookies(), f)

        print(f"[sp_tokens] Processing page {page_count}...")
        page_key = f"page_{page_count}"
        all_data[page_key] = extract_tokens_from_page()

        _, _, next_page_link, _ = get_table_links(driver, '//*[@id="tabList"]')
        if next_page_link:
            driver.get(next_page_link)
            page_count += 1
        else:
            break

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2)

    print(f"[sp_tokens] Saved all SP tokens -> {output_file}")
    print(f"[sp_tokens] Saved cookies -> {cookies_file}")



if __name__ == "__main__":
    try:
        # Apply filters
        time.sleep(3)


        #  Solve captcha + search
        captcha_input(driver, '//*[@id="captchaImage"]', '//*[@id="captchaText"]')
        time.sleep(0.5)
        # Extract SP tokens (and cookies)
        extract_sp_tokens_paginated(
            driver=driver,
            output_file=SP_TOKENS_PATH,
            cookies_file=COOKIES_PATH,
        )

        # Run http_utils after sp tokens exist

        http_utils.COOKIE_FILE = str(COOKIES_PATH)
        http_utils.OUTPUT_DIR = str(HTML_OUTPUT_DIR)
        http_utils.VIEW_MORE_SP_JSON_FILE = str(VIEW_MORE_SP_JSON_PATH)

        with open(SP_TOKENS_PATH, "r", encoding="utf-8") as f:
            sp_data = json.load(f)

        print(f"[http_utils] Saving HTML into -> {HTML_OUTPUT_DIR}")
        http_utils.save_html_responses(sp_data)
        print("[http_utils] HTML saving completed")

        # Run extract_tender after HTMLs are saved
 
        workers = min(16, (multiprocessing.cpu_count() or 4) * 2)
        print(f"[extract_tender] Extracting CSVs into -> {EXTRACTED_OUT_DIR} (workers={workers})")
        extract_tender.process_tree(
            root_dir=str(HTML_OUTPUT_DIR),
            out_dir=str(EXTRACTED_OUT_DIR),
            workers=workers,
            skip_existing=True,
        )
        print("[extract_tender] Extraction completed")

    except Exception as e:
        print(f"error: {e}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass
