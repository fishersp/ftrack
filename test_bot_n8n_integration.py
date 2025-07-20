#!/usr/bin/env python3
"""
Test script for validating the integration between Telegram bot and n8n
This script tests both the get-sheet and save-file workflows
"""

import requests
import pandas as pd
from io import BytesIO
import json
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s → %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("integration_test")

# Configuration
N8N_GET_URL = "https://protestant-charla-koelkellll-6e50472c.koyeb.app/webhook/get-sheet"
N8N_SAVE_URL = "https://protestant-charla-koelkellll-6e50472c.koyeb.app/webhook/save-file"

def test_get_sheet():
    """Test downloading Excel file from n8n"""
    log.info("Testing GET sheet from n8n...")
    
    try:
        # Send GET request to n8n
        resp = requests.get(N8N_GET_URL, timeout=30)
        log.info(f"GET response status: {resp.status_code}")
        log.info(f"Content-Type: {resp.headers.get('content-type')}")
        log.info(f"Content-Length: {resp.headers.get('content-length')}")
        
        # Check if response is valid
        if resp.status_code != 200:
            log.error(f"Error: Received status code {resp.status_code}")
            return False
            
        # Check content type
        content_type = resp.headers.get('content-type', '')
        if 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' not in content_type:
            log.warning(f"Warning: Content-Type is not Excel: {content_type}")
        
        # Try to read as Excel
        try:
            excel_data = BytesIO(resp.content)
            df = pd.read_excel(excel_data, sheet_name=None)
            log.info(f"Successfully read Excel file with sheets: {list(df.keys())}")
            
            # Check if "Трекер расходов" sheet exists
            if "Трекер расходов" in df:
                log.info(f"Found 'Трекер расходов' sheet with {len(df['Трекер расходов'])} rows")
            else:
                log.warning("Sheet 'Трекер расходов' not found in Excel file")
                
            return True
        except Exception as e:
            log.error(f"Error reading Excel file: {str(e)}")
            # Save response content for debugging
            with open("debug_response.bin", "wb") as f:
                f.write(resp.content)
            log.info("Saved response content to debug_response.bin for inspection")
            return False
            
    except Exception as e:
        log.error(f"Error in GET request: {str(e)}")
        return False

def test_save_file():
    """Test uploading data to n8n for saving to Excel"""
    log.info("Testing SAVE file to n8n...")
    
    try:
        # Test data
        test_data = {
            "дата": "2025-06-13",
            "категория": "TEST_CATEGORY",
            "сумма": "999",
            "комментарий": "Integration Test"
        }
        
        # Create a simple Excel file for testing
        output = BytesIO()
        df = pd.DataFrame([test_data])
        df.to_excel(output, sheet_name="Test", index=False)
        output.seek(0)
        
        # Send POST request to n8n
        files = {
            "file": ("test_file.xlsx", output, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        }
        
        resp = requests.post(N8N_SAVE_URL, files=files, data=test_data, timeout=30)
        log.info(f"POST response status: {resp.status_code}")
        
        # Check response
        if resp.status_code != 200:
            log.error(f"Error: Received status code {resp.status_code}")
            return False
            
        try:
            resp_json = resp.json()
            log.info(f"Response JSON: {json.dumps(resp_json, indent=2)}")
        except:
            log.info(f"Response text: {resp.text[:200]}")
            
        return True
        
    except Exception as e:
        log.error(f"Error in POST request: {str(e)}")
        return False

if __name__ == "__main__":
    log.info("Starting integration tests...")
    
    # Test GET workflow
    get_result = test_get_sheet()
    log.info(f"GET test {'PASSED' if get_result else 'FAILED'}")
    
    # Test POST workflow
    save_result = test_save_file()
    log.info(f"SAVE test {'PASSED' if save_result else 'FAILED'}")
    
    # Overall result
    if get_result and save_result:
        log.info("All tests PASSED!")
    else:
        log.error("Some tests FAILED!")
