from flask import Flask, render_template, request, jsonify
import pandas as pd
from db_config import get_connection

app = Flask(__name__)

# Correct column names based on actual table/CSV header, including spaces
# These are the columns to display in the summary table
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
    """
    conn = None
    try:
        conn = get_connection()
        # Quote column names for SQL query if they contain special characters
        select_cols_quoted = [
            f"[{col}]" if any(char in col for char in [' ', '.', '-', '/', '\\', '(', ')', '[', ']']) else col
            for col in SUMMARY_COLS
        ]
        query = f"SELECT {', '.join(select_cols_quoted)} FROM dbo.MLS_Master_Data1"
        
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
        return pd.DataFrame(columns=SUMMARY_COLS) # Return empty DataFrame on error
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
        # Ensure MLS_Point_Code is correctly quoted in the query
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
        selected_mls_code=selected_mls_code
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
    return render_template("details.html", info=info)

if __name__ == '__main__':
    app.run(debug=True)

