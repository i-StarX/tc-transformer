import os
import re
import json
import time
import pandas as pd
import requests
from io import BytesIO
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Form
from selenium import webdriver
from selenium.webdriver.common.by import By

# If you have your langchain_openai imports:
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage

# 1) Load environment variables from .env
load_dotenv()

# 2) Access environment variables
AZURE_OPENAI_API_BASE = os.getenv("AZURE_OPENAI_API_BASE")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION")

O1_MINI_DEPLOYMENT_NAME = os.getenv("O1_MINI_DEPLOYMENT_NAME", "o1-mini")
GPT_4O_MINI_DEPLOYMENT_NAME = os.getenv("GPT_4O_MINI_DEPLOYMENT_NAME", "gpt-4o-mini")

USERNAME = os.getenv("USERNAME", "standard_user")
PASSWORD = os.getenv("PASSWORD", "secret_sauce")

# 3) Setup your Azure OpenAI clients
o3_mini_model = AzureChatOpenAI(
    azure_endpoint=AZURE_OPENAI_API_BASE,
    api_key=AZURE_OPENAI_API_KEY,
    api_version=OPENAI_API_VERSION,
    deployment_name=O1_MINI_DEPLOYMENT_NAME,
    temperature=0
)

gpt4o_mini_model = AzureChatOpenAI(
    azure_endpoint=AZURE_OPENAI_API_BASE,
    api_key=AZURE_OPENAI_API_KEY,
    api_version=OPENAI_API_VERSION,
    deployment_name=GPT_4O_MINI_DEPLOYMENT_NAME,
    temperature=0
)

# 4) Create FastAPI app
app = FastAPI()

# -----------------------------------------------------------------------------
# Utility / code from your snippet
# -----------------------------------------------------------------------------

def group_by_goto_with_index(df):
    """
    Create groups of rows. Each time we hit a 'goto' action, 
    we start a new group. 
    We return a list of groups, each group is a list of dicts, 
    and each dict includes {"index": original_index, ... row_data }.
    """
    all_rows = df.reset_index().to_dict(orient="records")

    groups = []
    current_group = []

    for row_dict in all_rows:
        action = str(row_dict["Action"]).strip().lower()
        if action == "goto":
            if current_group:
                groups.append(current_group)
            current_group = [row_dict]
        else:
            current_group.append(row_dict)

    if current_group:
        groups.append(current_group)

    return groups


def extract_locators_from_html(html_content, actions):
    """
    Takes current page HTML and the list of non-'goto' actions to analyze.
    Returns JSON string from gpt-4o-mini, which should decode to 
    a list of objects (in the same order).
    """
    soup = BeautifulSoup(html_content, "html.parser")
    prompt = f"""
    You are an intelligent assistant that extracts web element locators for automated testing.

    Here is the HTML structure of the page (soup):
    {soup.prettify()}

    Based on the following test case data (each item is a row in the group, excluding 'goto'):
    {actions}

    For each action, extract the required details:
      - 'Locator Type' (e.g., locator, role, id)
      - 'Role (used if locator type is role)' (e.g., 'button', 'link')
      - 'Element Locator ' (the actual locator, e.g., [id="user-name"])
      - 'Element Name' (some descriptive name or ID)

    Return the result in valid JSON. The JSON must be an array of objects, 
    each object with these keys: ["Locator Type", "Role (used if locator type is role)", 
                                  "Element Locator ", "Element name"].
    The JSON array must match the order of 'actions'.
    """

    response = gpt4o_mini_model.invoke([HumanMessage(content=prompt)])
    return response.content


def generate_selenium_code_o3_mini(login_needed, url):
    prompt = f"""
    You are an assistant that generates Python Selenium code.
    Write a code snippet using:
    - from selenium import webdriver
    - from selenium.webdriver.common.by import By
    - driver.get()
    - minimal necessary steps to accomplish the required action(s).

    Requirements:
    1. If 'login_needed' is True, log in to https://www.saucedemo.com 
       with username={USERNAME} and password={PASSWORD}.
    2. Then navigate to the URL: {url}
    3. Return only Python code snippet (no markdown), no extra text.
    """

    response = o3_mini_model.invoke([HumanMessage(content=prompt)])
    return response.content


def run_selenium_snippet(driver, snippet):
    # remove any line that tries to (re)create driver
    lines = snippet.split("\n")
    filtered_lines = []
    for line in lines:
        if line.strip().startswith("driver = "):
            continue
        filtered_lines.append(line)
    safe_snippet = "\n".join(filtered_lines)

    local_scope = {"driver": driver, "webdriver": webdriver, "By": By, "time": time}
    exec(safe_snippet, {}, local_scope)


def process_test_cases_from_df(df):
    """
    This version works directly from a DataFrame (df).
    If you need to incorporate 'test_url' or user/pass, you can do so in 
    the snippet generation. 
    """
    df["Locator Type"] = ""
    df["Role (used if locator type is role)"] = ""
    df["Element Locator "] = ""
    df["Element name"] = ""

    groups = group_by_goto_with_index(df)

    driver = webdriver.Chrome()
    driver.implicitly_wait(5)

    for i, group in enumerate(groups):
        goto_step = group[0]
        url = goto_step.get("Test Data", "")

        snippet = generate_selenium_code_o3_mini(login_needed=(i == 0), url=url)
        print(f"\n--- Selenium code for Group {i+1} ---")
        print(snippet)

        run_selenium_snippet(driver, snippet)

        page_html = driver.page_source

        non_goto_rows = [r for r in group if str(r["Action"]).strip().lower() != "goto"]
        if not non_goto_rows:
            continue

        actions_for_extraction_data = []
        for row_dict in non_goto_rows:
            actions_for_extraction_data.append({
                "TC Reference": row_dict.get("TC Reference", ""),
                "Test case description": row_dict.get("Test case description", ""),
                "Expected outcome": row_dict.get("Expected outcome", ""),
                "Actual outcome": row_dict.get("Actual outcome", ""),
                "Action": row_dict.get("Action", "")
            })

        extraction_json_str = extract_locators_from_html(page_html, actions_for_extraction_data)
        print(f"\n--- Extracted Locator Details for Group {i+1} ---")
        print(extraction_json_str)

        # Remove code fence if present
        extraction_json_str = re.sub(r"^```(?:json)?\s*", "", extraction_json_str)
        extraction_json_str = re.sub(r"\s*```$", "", extraction_json_str)
        extraction_json_str = extraction_json_str.strip()

        # Attempt to fix [id="..."] patterns
        fixed_str = re.sub(
            r'\[id="([^"]+)"\]', 
            lambda m: f'[id=\\"{m.group(1)}\\"]', 
            extraction_json_str
        )

        try:
            extraction_results = json.loads(fixed_str)
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            extraction_results = []

        for idx, row_dict in enumerate(non_goto_rows):
            original_index = row_dict["index"]
            if idx < len(extraction_results):
                loc = extraction_results[idx]
                df.at[original_index, "Locator Type"] = loc.get("Locator Type", "")
                df.at[original_index, "Role (used if locator type is role)"] = loc.get("Role (used if locator type is role)", "")
                df.at[original_index, "Element Locator "] = loc.get("Element Locator ", "")
                df.at[original_index, "Element name"] = loc.get("Element name", "")

    driver.quit()

    desired_cols = [
        "TC Reference",
        "Test case description",
        "Expected outcome",
        "Actual outcome",
        "Action",
        "Locator Type",
        "Role (used if locator type is role)",
        "Element Locator ",
        "Element name"
    ]
    final_cols = [c for c in desired_cols if c in df.columns]
    final_df = df[final_cols].copy()
    return final_df

# -----------------------------------------------------------------------------
# FASTAPI Endpoint
# -----------------------------------------------------------------------------

@app.post("/process-test-cases")
async def process_test_cases_endpoint(
    file: UploadFile = File(...),
    test_url: str = Form(...)
):
    """
    1. We receive an Excel file (UploadFile) + a form field test_url.
    2. We read the file in memory, load into a DataFrame.
    3. We pass the DF to 'process_test_cases_from_df'.
    4. We return the final DataFrame as JSON.
    """

    # 1. Read the uploaded Excel into a DataFrame
    contents = await file.read()
    excel_buffer = BytesIO(contents)
    df = pd.read_excel(excel_buffer, header=0)

    # 2. Optionally, do something with 'test_url'. 
    #    e.g., If you'd like to store it in the DF or pass it to the snippet, 
    #    you can add logic. For now, we just store it in a column if you like:
    df["Test Data"] = df["Test Data"].fillna("")  # ensure no NaN
    # If you'd prefer to override all URLs with test_url, do something like:
    # df["Test Data"] = test_url

    # 3. Process
    final_df = process_test_cases_from_df(df)

    # 4. Return the final DF as JSON
    #    We'll use DataFrame.to_dict(...) to convert
    return final_df.to_dict(orient="records")


### cURL

# curl -X POST "http://127.0.0.1:8000/process-test-cases" \
#   -F "file=@/path/to/your/input.xlsx" \
#   -F "test_url=https://www.saucedemo.com" \
#   -F "username=standard_user" \
#   -F "password=secret_sauce"
