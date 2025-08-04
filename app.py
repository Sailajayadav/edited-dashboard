from flask import Flask, render_template, request, jsonify
import pandas as pd
from db_config import get_connection
import pyodbc # Import pyodbc for direct SQL execution

app = Flask(__name__)

# Columns to display in the summary table on index.html
SUMMARY_COLS = [
    "MLS_Point_Code",
    "MLS_Point_Name",
    "Mandal_Name",
    "District_Name",
    "MLS_Point_Incharge_Name",
    "Storage_Capacity_in"
]

# Columns to use for dropdown filters
FILTER_COLS = [
    "District_Name",
    "Mandal_Name",
    "MLS_Point_Name",
    "MLS_Point_Code"
]

# Columns that can be updated from the UI (both index.html and details.html).
# IMPORTANT: These MUST match your actual database column names exactly (case-sensitive).
# Adjust this list based on your database schema and what you want users to edit.
EDITABLE_COLS = [
    "S_No", # From your screenshot
    "District_Code", # From your screenshot
    "District_Name",
    "Mandal_Code", # From your screenshot
    "Mandal_Name",
    "MLS_Point_Code",
    "MLS_Point_Name",
    "MLS_Point_Latitude", # From your screenshot
    "MLS_Point_Logitude", # From your screenshot
    "MLS_Point_Address",  # From your screenshot
    "MLS_Point_Incharge_Name",
    "MLS_Point_Incharge_CFMS_Corporation_EMP", # From your screenshot
    "Storage_Capacity_in",
    "Contact_Number",
    "Email_ID",
    "Status",
    "Last_Updated" # Consider if this should be automatically managed by DB or manually editable
]

def get_unique_values(column_name, filter_column=None, filter_value=None):
    """
    Fetches unique values for a given column from the dbo.MLS_Master_Data1 table.
    Can optionally filter based on another column's value.
    Handles column names with special characters by enclosing them in square brackets.
    """
    conn = None
    try:
        conn = get_connection()
        # Enclose column name in square brackets for SQL Server if it contains spaces or other special characters
        quoted_column_name = f"[{column_name}]" if any(char in column_name for char in [' ', '.', '-', '/', '\\', '(', ')', '[', ']']) else column_name
        
        query = f"SELECT DISTINCT {quoted_column_name} FROM dbo.MLS_Master_Data1"
        params = []
        
        if filter_column and filter_value and filter_value != "All":
            quoted_filter_column = f"[{filter_column}]" if any(char in filter_column for char in [' ', '.', '-', '/', '\\', '(', ')', '[', ']']) else filter_column
            query += f" WHERE {quoted_filter_column} = ?"
            params.append(filter_value)
            
        query += f" ORDER BY {quoted_column_name}"

        df = pd.read_sql(query, conn, params=params)
        # Convert to list, filtering out None/NaN values if any
        return [str(val) for val in df.iloc[:, 0].dropna().unique()]
    except Exception as e:
        print(f"Error fetching unique values for {column_name} with filter {filter_column}={filter_value}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_filtered_summary(district=None, mandal=None, mls_name=None, mls_code=None):
    """
    Fetches MLS summary data based on provided filter criteria.
    Constructs a dynamic SQL WHERE clause.
    Fetches *all* columns (SELECT *) to support comprehensive editing in the details page.
    """
    conn = None
    try:
        conn = get_connection()
        query = f"SELECT * FROM dbo.MLS_Master_Data1"
        
        conditions = []
        params = []

        if district and district != "All":
            conditions.append("[District_Name] = ?")
            params.append(district)
        if mandal and mandal != "All":
            conditions.append("[Mandal_Name] = ?")
            params.append(mandal)
        if mls_name and mls_name != "All":
            conditions.append("[MLS_Point_Name] = ?")
            params.append(mls_name)
        if mls_code and mls_code != "All":
            conditions.append("[MLS_Point_Code] = ?")
            params.append(mls_code)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        df = pd.read_sql(query, conn, params=params)
        return df
    except Exception as e:
        print(f"Error fetching filtered summary: {e}")
        return pd.DataFrame(columns=[]) # Return empty DataFrame on error
    finally:
        if conn:
            conn.close()

def get_details(mls_code):
    """
    Fetches all details for a specific MLS point by its code.
    """
    conn = None
    try:
        conn = get_connection()
        df = pd.read_sql(
            "SELECT * FROM dbo.MLS_Master_Data1 WHERE [MLS_Point_Code] = ?", conn, params=[mls_code]
        )
        return df.iloc[0].to_dict() if not df.empty else None
    except Exception as e:
        print(f"Error fetching details for MLS Point Code {mls_code}: {e}")
        return None
    finally:
        if conn:
            conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    # Get unique values for initial dropdowns
    districts = get_unique_values("District_Name")
    
    # Initialize selected filters from form or default to "All"
    selected_district = request.form.get('district_name', 'All')
    selected_mandal = request.form.get('mandal_name', 'All')
    selected_mls_name = request.form.get('mls_point_name', 'All')
    selected_mls_code = request.form.get('mls_point_code', 'All')

    # Dynamically get mandals based on selected_district
    mandals = get_unique_values("Mandal_Name", "District_Name", selected_district)
    
    # Dynamically get MLS names based on selected_mandal (which is influenced by selected_district)
    mls_names = get_unique_values("MLS_Point_Name", "Mandal_Name", selected_mandal)
    mls_codes = get_unique_values("MLS_Point_Code", "Mandal_Name", selected_mandal)

    if request.method == 'POST':
        # Fetch filtered records based on all selected criteria
        records_df = get_filtered_summary(
            selected_district,
            selected_mandal,
            selected_mls_name,
            selected_mls_code
        )
    else:
        # On initial GET request, fetch all records
        records_df = get_filtered_summary() # Call without filters to get all

    # Convert DataFrame to a list of dictionaries for Jinja2 template
    records = records_df.to_dict(orient="records")

    return render_template(
        "index.html",
        records=records,
        districts=districts,
        mandals=mandals,
        mls_names=mls_names,
        mls_codes=mls_codes,
        selected_district=selected_district,
        selected_mandal=selected_mandal,
        selected_mls_name=selected_mls_name,
        selected_mls_code=selected_mls_code,
        summary_cols=SUMMARY_COLS # Pass this to render only summary cols initially
    )

@app.route('/get_mandals/<district_name>')
def get_mandals_for_district(district_name):
    """
    API endpoint to return mandals based on the selected district.
    """
    mandals = get_unique_values("Mandal_Name", "District_Name", district_name)
    return jsonify(mandals)

@app.route('/get_mls_points/<mandal_name>')
def get_mls_points_for_mandal(mandal_name):
    """
    API endpoint to return MLS Point Names based on the selected mandal.
    """
    mls_points = get_unique_values("MLS_Point_Name", "Mandal_Name", mandal_name)
    return jsonify(mls_points)

@app.route('/get_mls_codes/<mandal_name>')
def get_mls_codes_for_mandal(mandal_name):
    """
    API endpoint to return MLS Point Codes based on the selected mandal.
    """
    mls_codes = get_unique_values("MLS_Point_Code", "Mandal_Name", mandal_name)
    return jsonify(mls_codes)

@app.route('/details/<mls_code>')
def details(mls_code):
    info = get_details(mls_code)
    if not info:
        return "No details found", 404
    # Pass EDITABLE_COLS to the details template
    return render_template("details.html", info=info, editable_cols=EDITABLE_COLS)

@app.route('/update_mls_data', methods=['POST'])
def update_mls_data():
    data = request.json
    mls_point_code = data.get('MLS_Point_Code')
    column_name = data.get('column')
    new_value = data.get('value')

    if not mls_point_code or not column_name or new_value is None:
        return jsonify({"success": False, "message": "Missing data"}), 400

    # Sanitize column_name to prevent SQL injection for column names
    # This check ensures only predefined columns can be updated
    if column_name not in EDITABLE_COLS:
        return jsonify({"success": False, "message": f"Column '{column_name}' is not editable or does not exist."}), 403

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Enclose column name in square brackets for SQL Server if it contains spaces or other special characters
        quoted_column_name = f"[{column_name}]" if any(char in column_name for char in [' ', '.', '-', '/', '\\', '(', ')', '[', ']']) else column_name
        
        # SQL UPDATE statement
        sql_query = f"UPDATE dbo.MLS_Master_Data1 SET {quoted_column_name} = ? WHERE [MLS_Point_Code] = ?"
        cursor.execute(sql_query, new_value, mls_point_code)
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({"success": False, "message": "No record found or no changes made."}), 404

        return jsonify({"success": True, "message": "Data updated successfully"})
    except Exception as e:
        print(f"Error updating data: {e}")
        return jsonify({"success": False, "message": f"Database error: {e}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/add_mls_data', methods=['POST'])
def add_mls_data():
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    # Filter data to only include columns that are present in the table and are part of EDITABLE_COLS
    cols_to_insert = [col for col in data.keys() if col in EDITABLE_COLS]
    
    # Check if MLS_Point_Code is provided for new record, as it's the primary key
    if "MLS_Point_Code" not in cols_to_insert or not data["MLS_Point_Code"]:
        return jsonify({"success": False, "message": "MLS_Point_Code is required for adding a new record."}), 400

    # Generate column names and placeholders for the SQL query
    quoted_cols = [f"[{col}]" if any(char in col for char in [' ', '.', '-', '/', '\\', '(', ')', '[', ']']) else col for col in cols_to_insert]
    placeholders = ", ".join(["?"] * len(quoted_cols))
    column_names_str = ", ".join(quoted_cols)
    values = [data[col] for col in cols_to_insert]

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql_query = f"INSERT INTO dbo.MLS_Master_Data1 ({column_names_str}) VALUES ({placeholders})"
        cursor.execute(sql_query, *values)
        conn.commit()
        return jsonify({"success": True, "message": "New record added successfully"})
    except pyodbc.IntegrityError as e:
        # Catch specific errors like primary key violation
        if "Violation of PRIMARY KEY constraint" in str(e):
            return jsonify({"success": False, "message": "MLS Point Code already exists. Please use a unique code."}), 409
        return jsonify({"success": False, "message": f"Database error: {e}"}), 500
    except Exception as e:
        print(f"Error adding new record: {e}")
        return jsonify({"success": False, "message": f"Error adding record: {e}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/delete_mls_data', methods=['POST'])
def delete_mls_data():
    data = request.json
    mls_point_code = data.get('MLS_Point_Code')

    if not mls_point_code:
        return jsonify({"success": False, "message": "MLS Point Code is required for deletion"}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql_query = "DELETE FROM dbo.MLS_Master_Data1 WHERE [MLS_Point_Code] = ?"
        cursor.execute(sql_query, mls_point_code)
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"success": False, "message": "Record not found"}), 404
        return jsonify({"success": True, "message": "Record deleted successfully"})
    except Exception as e:
        print(f"Error deleting record: {e}")
        return jsonify({"success": False, "message": f"Database error: {e}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    app.run(debug=True)