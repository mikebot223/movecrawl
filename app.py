import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import urllib.parse
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()
openai_api_key = os.getenv('OPENAI_API_KEY')

# Initialize OpenAI client
openai_client = OpenAI(api_key=openai_api_key)

def scrape_website(url):
    # Initialize Chrome options for Selenium
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")  # Ensures Chrome runs in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Initialize the Chrome driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    # Set default values for variables
    cameleon_text = "Not found"
    footer_text = "Not found"
    page_title = "Not found"

    # Open the website
    driver.get(url)
    driver.implicitly_wait(10)

    try:
        page_title = driver.title
        
        try:
            cameleon_p = driver.find_element(By.CSS_SELECTOR, '#cameleon > p')
            cameleon_text = cameleon_p.text.strip()
        except NoSuchElementException:
            cameleon_text = "Not found"

        try:
            footer = driver.find_element(By.TAG_NAME, 'footer')
            footer_text = footer.text.strip()
        except NoSuchElementException:
            footer_text = "Not found"
    
    except Exception as e:
        st.error(f"An error occurred: {e}")

    finally:
        driver.quit()

    return page_title, cameleon_text, footer_text

def query_openai(cameleon_text, footer_text, page_title):
    content_to_analyze = f"{cameleon_text} \n{footer_text} \n{page_title}"
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Your job is to extract only the asked information from the given text, nothing more. Make sure to provide your answers as concise as possible."},
            {"role": "user", "content": f"What is the company name here, please only return the company name from the given text exactly as it is spelled: \n{content_to_analyze}"}
        ],
        top_p=0.5,
        temperature=0.2,
        max_tokens=150,
    )

    comp_name = response.choices[0].message.content.strip()
    return comp_name

def scrape_bbb_for_company_info(company_name):
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36")

    with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options) as driver:
        encoded_company_name = urllib.parse.quote(company_name)
        search_url = f"https://www.bbb.org/search?find_country=CAN&find_text={encoded_company_name}&page=1&sort=Relevance"
        driver.get(search_url)
        info = {}

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "h3.bds-h4 > a.text-blue-medium"))
            )
            company_links = driver.find_elements(By.CSS_SELECTOR, "h3.bds-h4 > a.text-blue-medium")
        except TimeoutException:
            company_links = []
            
            for link in company_links:
                if company_name.lower() in link.text.lower():
                    link.click()  # Click on the link if the company name matches
                    break  # Exit the loop after clicking the matching link
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            
            # Example for customer reviews text
            try:
                info['Customer Reviews Text'] = driver.find_element(By.CSS_SELECTOR, "p.bds-body.text-size-5").text
            except NoSuchElementException:
                info['Customer Reviews Text'] = "Customer review"
