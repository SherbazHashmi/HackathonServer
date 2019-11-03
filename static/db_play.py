import pyodbc

# Set up the connection with server database
cnxn = pyodbc.connect("Driver={SQL Server Native Client 11.0};"
                      "Server=DESKTOP-R9C393K;"
                      "Database=model;"
                      "Trusted_Connection=yes;")

print("database got connected")

cursor = cnxn.cursor()
print("cursor is ready")

# an quick demo:

"""
sql_select_Query = "CREATE TABLE [model].[dbo].[TEST] (TEST nvarchar(255) NULL);"
cursor.execute(sql_select_Query)
cursor.commit()
"""

cursor.close()
cnxn.close()
