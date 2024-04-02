import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException
from openai import OpenAI
import os
from dotenv import load_dotenv
import cohere
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import urllib.parse




# Load environment variables
load_dotenv()
openai_api_key = os.getenv('OPENAI_API_KEY')
# cohere_api_key = os.getenv('COHERE_API_KEY')

# Initialize OpenAI and Cohere clients
openai_client = OpenAI(api_key=openai_api_key)
# cohere_client = cohere.Client(api_key=cohere_api_key)

def scrape_website(url):
    # Initialize Chrome options for Selenium
    chrome_options = Options()
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36")


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

def query_openai(comp_name, cameleon_text, footer_text, page_title):
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

def summary_comp(comp_name, bbb_info):
    for key, value in bbb_info.items():
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Your job is to summarize the company outlook based on the provided information."},
                {"role": "user", "content": f"What is the company outlook for this {comp_name}, based on the following information **{key}:** {value}"}
            ],
            top_p=0.5,
            temperature=0.2,
            max_tokens=300,
        )

    summary = response.choices[0].message.content.strip()
    return summary

# def query_cohere(comp_name, url):
#     response = cohere_client.chat(
#         message=f"What is the address of the following moving company use the following link only {url}  here is the company name {comp_name}. If you cannot find the address in the provided website, look up {comp_name} in https://bbb.org/ . Also check the google reviews for {comp_name} and provide the information accordingly",
#         connectors=[{"id": "web-search"}],
#         temperature=0.1
#     )
#     return response.text

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
            try:
                rating_numeric = driver.find_element(By.CSS_SELECTOR, ".bds-body.text-size-70").text.split('/')[0].strip()
                info['Rating (Numeric)'] = f"{rating_numeric} / 5"
            except NoSuchElementException:
                info['Rating (Numeric)'] = "Numeric rating information is not available."

            # Check for "Accredited Since" and accreditation status
            try:
                accredited_since = driver.find_element(By.XPATH, "//p[contains(., 'Accredited Since:')]").text
                info['Accredited Since'] = accredited_since.split(': ')[1]
            except NoSuchElementException:
                try:
                    non_accredited_notice = driver.find_element(By.XPATH, "//a[contains(text(), 'This business is not BBB Accredited')]").text
                    info['Accreditation Status'] = non_accredited_notice
                except NoSuchElementException:
                    info['Accreditation Status'] = "Accreditation information is not available."

            # Extract "Years in Business" if available
            try:
                years_in_business = driver.find_element(By.XPATH, "//p[contains(., 'Years in Business:')]").text
                info['Years in Business'] = years_in_business.split(': ')[1]
            except NoSuchElementException:
                info['Years in Business'] = "Years in Business information is not available."

        except TimeoutException:
            st.error("Timed out waiting for page elements to load.")
        except Exception as e:
            st.error(f"An error occurred: {e}")

        return info
# Streamlit app
def main():
    st.title("Website Information Extractor")
    
    # Input from user
    user_url = st.text_input("Enter the URL of the website:")

    if st.button("Extract Information"):
        if user_url:
            page_title, cameleon_text, footer_text = scrape_website(user_url)
            comp_name = query_openai(page_title, cameleon_text, footer_text, user_url)
            # cohere_response = query_cohere(comp_name, user_url)
            
            # Display extracted information
            # st.write("### Extracted Information")
            # st.write(f"**Page Title:** {page_title}")
            # st.write(f"**Cameleon Text:** {cameleon_text}")
            # st.write(f"**Footer Text:** {footer_text}")
            st.write(f"**Company Name:** {comp_name}")
            bbb_info = scrape_bbb_for_company_info(comp_name)
            st.write("### BBB Information")
            for key, value in bbb_info.items():
                st.write(f"**{key}:** {value}")
            
            # st.write("### Cohere Response")
            # st.write(cohere_response)
            summary=summary_comp(comp_name,bbb_info)
            st.write(summary)
        else:
            st.error("Please enter a URL to extract information.")

if __name__ == "__main__":
    main()
