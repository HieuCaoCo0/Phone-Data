import time
# import re
import pandas as pd

from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def get_brand_urls(driver):
    # Truy cap link
    driver.get("https://www.gsmarena.com/makers.php3")
    
    # Lay URL cua tat ca hang
    links = driver.find_elements(
        By.CSS_SELECTOR,
        "div.main-makers div.st-text a[href]"
    )
    print("Lấy url của tất cả các hãng thành công!")

    brands = []
    for link in links:
        # print(link.text)
        # print(link.get_attribute("href"))
        # print("-" * 40)
        name = link.text.strip().split()[0]
        href = link.get_attribute("href")

        if href:
            brands.append({
                "brand":name,
                "brand_url":href
            })
    
    print("Tổng số hăng: ", len(brands))
    return brands

def get_device_urls(driver, brand):
    current_url = brand["brand_url"]
    visited_pages = set()
    devices = []

    while current_url and current_url not in visited_pages:
        visited_pages.add(current_url)

        print("Đang truy cập:", current_url)
        driver.get(current_url)

        links = driver.find_elements(
            By.CSS_SELECTOR,
            "div.makers ul li a[href]"
        )

        for link in links:
            href = link.get_attribute("href")

            try:
                name = link.find_element(
                    By.CSS_SELECTOR, "strong span"
                ).text.strip()
            except Exception:
                continue

            if not href or not name:
                continue

            devices.append({
                "brand": brand["brand"],
                "device_name": name,
                "device_url": href
            })

        next_links = driver.find_elements(
            By.CSS_SELECTOR,
            "div.review-nav-v2 a.prevnextbutton[title='Next page']"
        )

        if not next_links:
            break

        next_url = next_links[0].get_attribute("href")

        if not next_url or next_url == "#":
            break

        current_url = next_url

        time.sleep(1)

    return devices

def scrapper_url():
    driver = webdriver.Chrome()
    all_devices = []

    try:
        brands = get_brand_urls(driver)

        print("Số hãng:", len(brands))

        for index, brand in enumerate(brands, start=1):
            print(
                f"\n[{index}/{len(brands)}] "
                f"{brand['brand']}"
            )

            devices = get_device_urls(driver, brand)
            all_devices.extend(devices)

            # Lưu tạm sau mỗi hãng
            df = pd.DataFrame(all_devices)
            df = df.drop_duplicates(subset=["device_url"])

            df.to_csv(
                "urls.csv",
                index=False,
                encoding="utf-8-sig"
            )

            time.sleep(1)

    finally:
        driver.quit()

    
        

if __name__ == "__main__":
    scrapper_url()
