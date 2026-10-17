import csv
import re
import time
import random
from pathlib import Path

from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait

# 1. CẤU HÌNH
BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "urls.csv"
OUTPUT_FILE = BASE_DIR / "raw_data1.csv"

START_ROW = 144
END_ROW = 14892

MIN_DELAY = 5   # Thời gian nghỉ tối thiểu giữa các trang (giây)
MAX_DELAY = 12   # Thời gian nghỉ tối đa giữa các trang (giây)
WAIT_TIMEOUT = 25 
MAX_RETRIES = 3 # Số lần thử lại tối đa nếu request lỗi/bị chặn
RELAUNCH_DRIVER_EVERY = 150 # Khởi động lại Chrome sau mỗi 150 thiết bị để tránh tràn bộ nhớ

# 2. CÁC CỘT ĐẦU RA
FIELDS = [
    "brand",
    "device_name",
    "device_url",
    "launch_announced",
    "body_dimensions",
    "body_weight",
    "display_type",
    "display_size",
    "display_resolution",
    "platform_os",
    "platform_chipset",
    "platform_cpu",
    "platform_gpu",
    "main_camera",
    "selfie_camera",
    "memory_internal",
    "battery_type",
    "battery_charging",
]

def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()

def get_spec(soup, data_spec):
    element = soup.select_one(f'td.nfo[data-spec="{data_spec}"]')
    if element is None:
        return ""
    return clean_text(element.get_text(" ", strip=True))

def get_number(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

def get_camera_type(soup, data_spec):
    element = soup.select_one(f'td.nfo[data-spec="{data_spec}"]')
    if element is None:
        return ""
    row = element.find_parent("tr")
    if row is None:
        return ""
    label = row.select_one("td.ttl")
    if label is None:
        return ""
    camera_type = clean_text(label.get_text(" ", strip=True)).lower()
    if camera_type == "single":
        return "Single"
    if camera_type == "dual":
        return "Dual"
    return ""

def get_battery_charging(soup):
    for row in soup.select("tr"):
        label = row.select_one("td.ttl")
        if label is None:
            continue
        label_text = clean_text(label.get_text(" ", strip=True)).lower()
        if label_text == "charging":
            value = row.select_one("td.nfo")
            if value is not None:
                return clean_text(value.get_text(" ", strip=True))
    return ""

def scrape_device(driver, device):
    url = device.get("device_url", "").strip()
    if not url:
        raise ValueError("Thiếu device_url")

    driver.get(url)

    WebDriverWait(driver, WAIT_TIMEOUT).until(
        lambda d: d.find_elements("css selector", "td.nfo[data-spec]")
    )

    # Nghỉ ngẫu nhiên để giống hành vi người thật, tránh bị chặn
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    soup = BeautifulSoup(driver.page_source, "html.parser")

    launch_announced = get_spec(soup, "year")
    body_dimensions = get_spec(soup, "dimensions")
    body_weight = get_spec(soup, "weight")

    display_type_raw = get_spec(soup, "displaytype")
    display_size_raw = get_spec(soup, "displaysize")
    display_resolution_raw = get_spec(soup, "displayresolution")

    display_type = get_number(r"(\d+(?:\.\d+)?)\s*Hz\b", display_type_raw)
    display_size = get_number(r"(\d+(?:\.\d+)?)\s*inches?\b", display_size_raw)
    
    resolution_match = re.search(r"(\d+\s*x\s*\d+)\s*pixels?\b", display_resolution_raw, re.IGNORECASE)
    display_resolution = ""
    if resolution_match:
        display_resolution = re.sub(r"\s+", " ", resolution_match.group(1)).strip()

    os_raw = get_spec(soup, "os")
    platform_os = os_raw.split(",")[0].strip() if os_raw else ""
    platform_chipset = get_spec(soup, "chipset")
    
    cpu_raw = get_spec(soup, "cpu")
    platform_cpu = re.sub(r"\s*\([^)]*\)", "", cpu_raw).strip()
    platform_gpu = get_spec(soup, "gpu")

    main_camera = get_camera_type(soup, "cam1modules")
    selfie_camera = get_camera_type(soup, "cam2modules")
    memory_internal = get_spec(soup, "internalmemory")
    battery_type = get_spec(soup, "batdescription1")
    battery_charging = get_battery_charging(soup)

    return {
        "brand": device.get("brand", "").strip(),
        "device_name": device.get("device_name", "").strip(),
        "device_url": url,
        "launch_announced": launch_announced,
        "body_dimensions": body_dimensions,
        "body_weight": body_weight,
        "display_type": display_type,
        "display_size": display_size,
        "display_resolution": display_resolution,
        "platform_os": platform_os,
        "platform_chipset": platform_chipset,
        "platform_cpu": platform_cpu,
        "platform_gpu": platform_gpu,
        "main_camera": main_camera,
        "selfie_camera": selfie_camera,
        "memory_internal": memory_internal,
        "battery_type": battery_type,
        "battery_charging": battery_charging,
    }

def get_completed_urls(output_file):
    """Đọc file output để lấy danh sách URL đã cào rồi, giúp chạy tiếp khi bị ngắt."""
    completed = set()
    if output_file.exists():
        with open(output_file, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("device_url") and row.get("launch_announced"): # Đảm bảo đã cào thành công
                    completed.add(row["device_url"])
    return completed

def create_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1366,900")
    options.add_argument("--disable-gpu")
    
    # Khởi tạo driver thông qua undetected-chromedriver để vô hiệu hóa hoàn toàn cơ chế chặn bot
    driver = uc.Chrome(options=options, use_subprocess=True)
    return driver

def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {INPUT_FILE}")

    with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        all_devices = list(reader)

    start_index = START_ROW - 2
    end_index = min(END_ROW - 1, len(all_devices))
    devices = all_devices[start_index:end_index]

    completed_urls = get_completed_urls(OUTPUT_FILE)
    
    file_exists = OUTPUT_FILE.exists()
    
    print(f"Tổng số thiết bị trong phạm vi: {len(devices)}")
    print(f"Đã cào trước đó: {len(completed_urls)} thiết bị. Sẽ bỏ qua các thiết bị này.")

    driver = create_driver()

    try:
        with open(OUTPUT_FILE, "a", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            
            if not file_exists or OUTPUT_FILE.stat().st_size == 0:
                writer.writeheader()

            success_count = 0
            for index, device in enumerate(devices):
                url = device.get("device_url", "").strip()
                device_name = device.get("device_name", "").strip()
                csv_row = start_index + index + 2

                if url in completed_urls:
                    continue

                print(f"\n[{index + 1}/{len(devices)}] Dòng CSV {csv_row}: {device_name}")

                # Thử lại tối đa MAX_RETRIES lần nếu gặp lỗi kết nối/chặn
                success = False
                last_error = None
                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        result = scrape_device(driver, device)
                        writer.writerow(result)
                        file.flush()
                        print("  Trạng thái: OK")
                        success = True
                        break
                    except Exception as error:
                        last_error = error
                        print(f"  Thử lại lần {attempt}/{MAX_RETRIES} do lỗi: {error}")
                        time.sleep(5 * attempt) # Nghỉ lâu hơn sau mỗi lần lỗi
                        
                        # Khởi động lại driver nếu lỗi có vẻ do đơ trình duyệt
                        try:
                            driver.quit()
                        except:
                            pass
                        driver = create_driver()

                if not success:
                    # Ghi dòng trống/lỗi để đánh dấu
                    writer.writerow({
                        "brand": device.get("brand", ""),
                        "device_name": device_name,
                        "device_url": url,
                    })
                    file.flush()
                    print(f"  Trạng thái: ERROR - Bỏ qua sau {MAX_RETRIES} lần thử. Lỗi: {last_error}")

                success_count += 1

                # Định kỳ làm mới Driver để giải phóng RAM
                if success_count % RELAUNCH_DRIVER_EVERY == 0:
                    print("--> Đang khởi động lại trình duyệt để làm mới tài nguyên...")
                    driver.quit()
                    time.sleep(3)
                    driver = create_driver()

        print(f"\nHoàn tất quá trình cào dữ liệu!")

    finally:
        if driver is not None:
            driver.quit()

if __name__ == "__main__":
    main()