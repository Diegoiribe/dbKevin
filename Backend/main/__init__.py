import os
from flask import Flask
from dotenv import load_dotenv

from flask_restful import Api
from flask_sqlalchemy import SQLAlchemy

api = Api()
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    load_dotenv()

    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://root:PyVpQmIPXZFbqIpWjWgBxYFWcfNyLuwW@autorack.proxy.rlwy.net:48045/railway"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    import main.resources as resources
    api.add_resource(resources.ClienteResource, '/cliente/<int:id>')
    api.add_resource(resources.ClientesResource, '/clientes')
    api.add_resource(resources.UsuarioResource, '/usuario/<int:id>')
    api.add_resource(resources.UsuariosResource, '/usuarios')
    api.init_app(app)


    return app

