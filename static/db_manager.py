import pyodbc
import json


class QueryConstructor:
    def __init__(self):
        pass

    def give_me_a_table(self, name, fields):
        template = "CREATE TABLE [model].[dbo].[{}] ({});"
        sub_template = "{} nvarchar(255) NULL"
        mapped_fileds = [sub_template.format("[{}]".format(field)) for field in fields]
        return template.format(name, ", ".join(mapped_fileds))

    def help_me_insert(self, name, data):
        template = "INSERT INTO [model].[dbo].[{}] VALUES ({});"
        data = ["'{}'".format(element) for element in data]
        return template.format(name, ", ".join(data))


class LazyJson:
    def __init__(self):
        pass

    def give_me_the_json(self, header, row):
        data = {}
        for zipped in zip(header, row):
            data[zipped[0]] = zipped[1]
        json_data = json.dumps(data)
        return json_data

    def handle_extracted_plants(self, extracted):
        header = ["name", "synonyms", "flowering", "distribution and occurrence"]
        # return a list of json objects
        return [self.give_me_the_json(header, row) for row in extracted]

    def handle_extracted_community(self, extracted):
        header = ["name", "description", "members", "visitors", "location", "id"]
        # return a list of json objects
        return [self.give_me_the_json(header, row) for row in extracted]

    def give_me_the_wrapped_plants(self, extratcted):
        wrapped = {}
        wrapped["Plants"] = self.handle_extracted_plants(extratcted)
        res = json.dumps(wrapped)
        return res

    def give_me_the_wrapped_community(self, extratcted):
        wrapped = {}
        wrapped["Community"] = self.handle_extracted_community(extratcted)
        res = json.dumps(wrapped)
        return res

    def make_me_normal_plants(self, extracted):
        stuff = self.give_me_the_wrapped_plants(extracted)
        stuff = json.loads(stuff)
        stuff[next(iter(stuff))] = [json.loads(element) for element in stuff[next(iter(stuff))]]
        return stuff

    def make_me_normal_community(self, extracted):
        stuff = self.give_me_the_wrapped_community(extracted)
        stuff = json.loads(stuff)
        stuff[next(iter(stuff))] = [json.loads(element) for element in stuff[next(iter(stuff))]]
        return stuff


class DataBaseManager:
    def __init__(self):
        self.cnxn = pyodbc.connect("Driver={SQL Server Native Client 11.0};"
                                   "Server=DESKTOP-R9C393K;"
                                   "Database=model;"
                                   "Trusted_Connection=yes;")

        print("database got connected")

        self.cursor = self.cnxn.cursor()
        print("cursor is ready")

        self.sql_constructor = QueryConstructor()

    def gentle_execute(self, query):
        self.cursor.execute(query)
        self.cursor.commit()

    def grab_plants(self):
        sql_select_Query = "SELECT * FROM [model].[dbo].[Plants]"
        self.cursor.execute(sql_select_Query)
        data = self.cursor.fetchall()
        print('data got extracted successfully')
        return data

    def grab_community(self):
        sql_select_Query = "SELECT * FROM [model].[dbo].[Community]"
        self.cursor.execute(sql_select_Query)
        data = self.cursor.fetchall()
        print('data got extracted successfully')
        return data

    def tear_down(self):
        self.cursor.close()
        self.cnxn.close()

    def create(self):
        pass

    def select(self):
        pass

    def delete(self):
        pass

    def update(self):
        pass


sql_helper = QueryConstructor()
db = DataBaseManager()
# stuff = sql_helper.help_me_insert("Plants",
#                                  ["name_data", "synonyms_data", "flowering_data", "distribution and occurrence_data"])
# for i in range(10):
#     db.gentle_execute(stuff)
# db.tear_down()

# print(db.grab_plants())
# cute_boy = LazyJson()
# print(cute_boy.give_me_the_wrapped_plants(db.grab_plants()).replace('"', '').replace("\"", "").replace('\\', ''))

# cute_boy = LazyJson()
# stuff = cute_boy.give_me_the_wrapped_plants(db.grab_plants())
# stuff = json.loads(stuff)
# stuff[next(iter(stuff))] = [json.loads(element) for element in stuff[next(iter(stuff))]]
# print()

# stuff = sql_helper.help_me_insert("Community",
#                                   ["name_data", "description_data", "members_data", "visitors_data", "location_data",
#                                    "id_data"])
# for i in range(10):
#     db.gentle_execute(stuff)
# db.tear_down()

# json_helper = LazyJson()
# db = DataBaseManager()
# print(json_helper.make_me_normal_community(db.grab_community()))

query = sql_helper.help_me_insert("Plants", [])
db.gentle_execute(query)
