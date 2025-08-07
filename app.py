# app.py
from flask import Flask, render_template, request, jsonify
import pandas as pd
import pyodbc

# Assuming db_config.py exists and works as provided
from db_config import get_connection

app = Flask(__name__)

# Columns to display on the main dashboard table
SUMMARY_COLS = [
    "MLS_Point_Code", "MLS_Point_Name", "Mandal_Name", "District_Name",
    "MLS_Point_Incharge_Name", "Storage_Capacity_in"
]

# Columns that can be updated from the UI.
# This list is used for both index.html (inline editing) and details.html
EDITABLE_COLS = [
    "S_No", "District_Code", "District_Name", "Mandal_Code", "Mandal_Name",
    "MLS_Point_Code", "MLS_Point_Name", "MLS_Point_Latitude", "MLS_Point_Logitude",
    "MLS_Point_Address", "MLS_Point_Incharge_Name", "MLS_Point_Incharge_CFMS_Corporation_EMP",
    "Storage_Capacity_in", "Contact_Number", "Email_ID", "Status", "Last_Updated"
]

def get_unique_values(column_name, filter_column=None, filter_value=None):
    conn = None
    try:
        conn = get_connection()
        quoted_column_name = f"[{column_name}]"
        query = f"SELECT DISTINCT {quoted_column_name} FROM dbo.MLS_Master_Data1"
        params = []
        if filter_column and filter_value and filter_value != "All":
            quoted_filter_column = f"[{filter_column}]"
            query += f" WHERE {quoted_filter_column} = ?"
            params.append(filter_value)
        query += f" ORDER BY {quoted_column_name}"
        df = pd.read_sql(query, conn, params=params)
        return [str(val) for val in df.iloc[:, 0].dropna().unique()]
    except Exception as e:
        print(f"Error fetching unique values for {column_name}: {e}")
        return []
    finally:
        if conn: conn.close()

def get_filtered_summary(district=None, mandal=None, mls_name=None, mls_code=None):
    conn = None
    try:
        conn = get_connection()
        query = "SELECT * FROM dbo.MLS_Master_Data1"
        conditions, params = [], []
        if district and district != "All": conditions.append("[District_Name] = ?"); params.append(district)
        if mandal and mandal != "All": conditions.append("[Mandal_Name] = ?"); params.append(mandal)
        if mls_name and mls_name != "All": conditions.append("[MLS_Point_Name] = ?"); params.append(mls_name)
        if mls_code and mls_code != "All": conditions.append("[MLS_Point_Code] = ?"); params.append(mls_code)
        if conditions: query += " WHERE " + " AND ".join(conditions)
        df = pd.read_sql(query, conn, params=params)
        return df
    except Exception as e:
        print(f"Error fetching filtered summary: {e}")
        return pd.DataFrame(columns=[])
    finally:
        if conn: conn.close()

def get_details(mls_code):
    conn = None
    try:
        conn = get_connection()
        df = pd.read_sql("SELECT * FROM dbo.MLS_Master_Data1 WHERE [MLS_Point_Code] = ?", conn, params=[mls_code])
        record_dict = df.iloc[0].where(pd.notnull(df.iloc[0]), None).to_dict() if not df.empty else None
        return record_dict
    except Exception as e:
        print(f"Error fetching details for MLS Point Code {mls_code}: {e}")
        return None
    finally:
        if conn: conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    selected_district = request.form.get('district_name', 'All')
    selected_mandal = request.form.get('mandal_name', 'All')
    selected_mls_name = request.form.get('mls_point_name', 'All')
    selected_mls_code = request.form.get('mls_point_code', 'All')

    records_df = get_filtered_summary(selected_district, selected_mandal, selected_mls_name, selected_mls_code)
    records = records_df.to_dict(orient="records")

    districts = get_unique_values("District_Name")
    mandals = get_unique_values("Mandal_Name", "District_Name", selected_district)
    mls_names = get_unique_values("MLS_Point_Name", "Mandal_Name", selected_mandal)
    mls_codes = get_unique_values("MLS_Point_Code", "Mandal_Name", selected_mandal)

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
        summary_cols=SUMMARY_COLS,
        editable_cols=[col for col in EDITABLE_COLS if col in SUMMARY_COLS]
    )

@app.route('/details/<mls_code>')
def details(mls_code):
    info = get_details(mls_code)
    if not info:
        return "No details found for this MLS Point.", 404
    
    # This is where we will pass the info object to the details page.
    # We will pass all the data, even if it's not a direct column in the main table.
    return render_template("details.html", info=info)

# Added routes for dynamic dropdowns
@app.route('/get_mandals/<district_name>')
def get_mandals_json(district_name):
    mandals = get_unique_values("Mandal_Name", "District_Name", district_name)
    return jsonify(mandals)

@app.route('/get_mls_names/<mandal_name>')
def get_mls_names_json(mandal_name):
    mls_names = get_unique_values("MLS_Point_Name", "Mandal_Name", mandal_name)
    return jsonify(mls_names)

@app.route('/get_mls_codes/<mandal_name>')
def get_mls_codes_json(mandal_name):
    mls_codes = get_unique_values("MLS_Point_Code", "Mandal_Name", mandal_name)
    return jsonify(mls_codes)

@app.route('/update_mls_data', methods=['POST'])
def update_mls_data():
    data = request.json
    mls_point_code = data.get('MLS_Point_Code')
    column_name = data.get('column')
    new_value = data.get('value')
    if not mls_point_code or not column_name or new_value is None:
        return jsonify({"success": False, "message": "Missing data"}), 400
    
    # Ensure the column name is in the list of editable columns to prevent SQL injection
    if column_name not in EDITABLE_COLS:
        return jsonify({"success": False, "message": f"Column '{column_name}' is not editable."}), 403
    
    conn, cursor = None, None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        quoted_column_name = f"[{column_name}]"
        sql_query = f"UPDATE dbo.MLS_Master_Data1 SET {quoted_column_name} = ? WHERE [MLS_Point_Code] = ?"
        cursor.execute(sql_query, new_value, mls_point_code)
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"success": False, "message": "No record found or no changes made."}), 404
        return jsonify({"success": True, "message": "Data updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Database error: {e}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/add_mls_data', methods=['POST'])
def add_mls_data():
    data = request.json
    if not data or "MLS_Point_Code" not in data or not data["MLS_Point_Name"]:
        return jsonify({"success": False, "message": "MLS Point Code and Name are required."}), 400
    cols_to_insert = [col for col in data.keys() if col in EDITABLE_COLS]
    quoted_cols = [f"[{col}]" for col in cols_to_insert]
    placeholders = ", ".join(["?"] * len(quoted_cols))
    column_names_str = ", ".join(quoted_cols)
    values = [data[col] for col in cols_to_insert]
    conn, cursor = None, None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql_query = f"INSERT INTO dbo.MLS_Master_Data1 ({column_names_str}) VALUES ({placeholders})"
        cursor.execute(sql_query, *values)
        conn.commit()
        return jsonify({"success": True, "message": "New record added successfully"})
    except pyodbc.IntegrityError as e:
        return jsonify({"success": False, "message": "MLS Point Code already exists."}), 409
    except Exception as e:
        return jsonify({"success": False, "message": f"Database error: {e}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/delete_mls_data', methods=['POST'])
def delete_mls_data():
    data = request.json
    mls_point_code = data.get('MLS_Point_Code')
    if not mls_point_code:
        return jsonify({"success": False, "message": "MLS Point Code is required for deletion"}), 400
    conn, cursor = None, None
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
        return jsonify({"success": False, "message": f"Database error: {e}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
        
if __name__ == '__main__':
    app.run(debug=True)