from flask import Flask
from flask import json
from flask_cors import CORS
import arcpy
from arcpy import env
from os import path
from static.db_manager import DataBaseManager, LazyJson

app = Flask(__name__)
cors = CORS(app)


@app.route('/')
# @cross_origin()
def hello_world():
    try:
        workspace = r"C://Hackathon//server//data"
        file = r"Indicative_Land_Release_Program_202223.shp"
        file = path.join(workspace, file)
        description = arcpy.Describe(file)
        shapeType = description.shapeType
        d = {"shapetype": shapeType}
        return json.jsonify(d)
    except Exception as e:
        print(e)

    return "Hello World"


@app.route('/data/plants', methods=['GET'])
def get_data_plants():
    json_helper = LazyJson()
    db = DataBaseManager()
    json_res = json_helper.make_me_normal_plants(db.grab_plants())
    return json.jsonify(json_res)


@app.route('/data/community', methods=['GET'])
def get_data_community():
    json_helper = LazyJson()
    db = DataBaseManager()
    json_res = json_helper.make_me_normal_community(db.grab_community())
    return json.jsonify(json_res)


if __name__ == '__main__':
    app.run(host='192.168.137.1', port=5000)
