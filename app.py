from flask import Flask
from flask import json
from flask_cors import CORS
import arcpy
from arcpy import env
from os import path

app = Flask(__name__)
cors = CORS(app)


@app.route('/')
#@cross_origin()
def hello_world():
    try:
        workspace = r"C://Hackathon//server//data"
        file = r"Indicative_Land_Release_Program_202223.shp"
        file = path.join(workspace, file)
        description = arcpy.Describe(file)
        shapeType = description.shapeType
        d = {"shapeType" : shapeType}
        return json.jsonify(d)
    except Exception as e:
        print(e)

    return "Hello World"


if __name__ == '__main__':
    app.run()
