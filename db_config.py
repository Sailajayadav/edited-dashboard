import pyodbc

def get_connection():
    return pyodbc.connect(
        r"DRIVER={ODBC Driver 17 for SQL Server};"
        r"SERVER=LAPTOP-92IOSGMR\SQLEXPRESS;"
        r"DATABASE=mlss;"
        r"Trusted_Connection=yes;"
    )
