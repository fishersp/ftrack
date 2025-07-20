"""
Python code for n8n Code node to modify Excel file
This code should be adapted for use in the n8n Code node
"""

import io
import pandas as pd
from datetime import datetime

# Function to process Excel file
def process_excel_file(excel_binary, webhook_data):
    """
    Process Excel file with new data from webhook
    
    Args:
        excel_binary: Binary content of Excel file
        webhook_data: Data from webhook (category, amount, comment, etc.)
        
    Returns:
        Binary content of modified Excel file
    """
    try:
        # Read Excel file from binary data
        excel_io = io.BytesIO(excel_binary)
        
        # Load all sheets with their names
        excel_file = pd.ExcelFile(excel_io)
        all_sheets = {}
        
        for sheet_name in excel_file.sheet_names:
            all_sheets[sheet_name] = pd.read_excel(excel_io, sheet_name=sheet_name)
        
        # Get the "Трекер расходов" sheet or create it if it doesn't exist
        if "Трекер расходов" in all_sheets:
            df_tracker = all_sheets["Трекер расходов"]
        else:
            # Create new sheet with appropriate columns
            df_tracker = pd.DataFrame(columns=["дата", "категория", "сумма (₽)", "комментарий", "учитывается в анализе?"])
        
        # Normalize column names
        df_tracker.columns = df_tracker.columns.str.strip().str.lower()
        
        # Extract data from webhook
        date_str = webhook_data.get("дата", datetime.now().strftime("%Y-%m-%d"))
        category = webhook_data.get("категория", "")
        amount = webhook_data.get("сумма", "0")
        try:
            amount = float(amount.replace("₽", "").replace(" ", ""))
        except (ValueError, AttributeError):
            amount = 0
        comment = webhook_data.get("комментарий", "")
        
        # Create new row
        new_row = {
            "дата": date_str,
            "категория": category,
            "сумма (₽)": amount,
            "комментарий": comment,
            "учитывается в анализе?": "да"
        }
        
        # Add new row to dataframe
        df_tracker = pd.concat([df_tracker, pd.DataFrame([new_row])], ignore_index=True)
        
        # Update the sheet in all_sheets
        all_sheets["Трекер расходов"] = df_tracker
        
        # Write all sheets back to Excel file
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for sheet_name, df in all_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Get binary content
        output.seek(0)
        return output.getvalue()
        
    except Exception as e:
        # Log error and return original binary
        print(f"Error processing Excel file: {str(e)}")
        return excel_binary

# For n8n Code node, you would adapt this to:
"""
// Get binary data and webhook data
const excelBinary = $input.item.binary.data.data;
const webhookData = $input.item.json;

// Call Python function to process Excel file
const modifiedExcelBinary = await $python.processExcelFile(excelBinary, webhookData);

// Return modified Excel file
return [{
  json: { success: true },
  binary: { data: { data: modifiedExcelBinary, mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' } }
}];
"""
