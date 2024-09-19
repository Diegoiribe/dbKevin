import os
from flask import Flask
from dotenv import load_dotenv
from flask_cors import CORS
from flask_restful import Api
from flask_sqlalchemy import SQLAlchemy

api = Api()
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    load_dotenv()
    CORS(app)

    PATH = os.getenv("DATABASE_PATH")
    DB_NAME = os.getenv("DATABASE_NAME")
    if not os.path.exists(f"{PATH}{DB_NAME}"):
        os.chdir(f"{PATH}")
        file = os.open(f"{DB_NAME}", os.O_CREAT)

    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{PATH}{DB_NAME}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    import main.resources as resources
    api.add_resource(resources.ClienteResource, '/<username>/cliente/<int:id>')
    api.add_resource(resources.ClientesResource, '/<username>/clientes')
    api.add_resource(resources.UsuarioResource, '/usuario/<int:id>')
    api.add_resource(resources.UsuariosResource, '/usuarios')
    api.init_app(app)


    return app

