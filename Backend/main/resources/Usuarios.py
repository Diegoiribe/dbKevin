import boto3
from flask_restful import Resource
from flask import request, jsonify
from .. import db
from main.models import UsuarioModel
import os

# Configuración de S3
S3_BUCKET = "botkevin"
S3_REGION = "us-east-1"  # Ejemplo: "us-west-1"
S3_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
S3_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# Asegúrate de utilizar las variables correctas aquí
s3_client = boto3.client(
    "s3",
    aws_access_key_id=S3_ACCESS_KEY,  # Usar la variable extraída del entorno
    aws_secret_access_key=S3_SECRET_KEY,  # Usar la variable extraída del entorno
    region_name=S3_REGION
)

def upload_image_to_s3(image_data, filename):
    """Sube la imagen a S3 y devuelve la URL pública."""
    try:
        s3_client.put_object(Bucket=S3_BUCKET, Key=filename, Body=image_data)
        return f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{filename}"
    except Exception as e:
        raise ValueError(f"Error al subir la imagen a S3: {e}")

class Usuario(Resource):
    
    def get(self, id):
        usuario = db.session.query(UsuarioModel).get_or_404(id)
        return usuario.to_json()
    
    def delete(self, id):
        usuario = db.session.query(UsuarioModel).get_or_404(id)
        db.session.delete(usuario)
        db.session.commit()
        return '', 204
    
    def put(self, id):
        usuario = db.session.query(UsuarioModel).get_or_404(id)
        
        # Manejar el envío de archivos (imagen)
        if 'imagen' in request.files:
            imagen_file = request.files['imagen']
            # Subir la imagen a S3 y obtener la URL
            filename = f"{usuario.username}_imagen.jpg"
            usuario.imagen = upload_image_to_s3(imagen_file.read(), filename)
        
        # Obtener datos del cuerpo de la solicitud (JSON o formulario)
        data = request.form or request.get_json()
        usuario.username = data.get("username", usuario.username)
        usuario.email = data.get("email", usuario.email)
        usuario.password = data.get("password", usuario.password)
        usuario.active = data.get("active", usuario.active)
        
        db.session.commit()
        return usuario.to_json(), 201

class Usuarios(Resource):
    
    def get(self):
        usuarios = db.session.query(UsuarioModel).all()
        return jsonify([usuario.to_json() for usuario in usuarios])
    
    def post(self):
        # Manejar imagen
        imagen_file = request.files.get('imagen')
        imagen_url = None
        
        if imagen_file:
            # Subir la imagen a S3 y obtener la URL
            filename = f"{request.form.get('username')}_imagen.jpg"
            imagen_url = upload_image_to_s3(imagen_file.read(), filename)
        
        # Manejar otros datos del formulario o JSON
        data = request.form or request.get_json()
        usuario = UsuarioModel(
            username=data.get("username"),
            email=data.get("email"),
            password=data.get("password"),
            active=data.get("active", True),  # Valor por defecto a True
            imagen=imagen_url  # Almacenar la URL de la imagen si existe
        )
        
        db.session.add(usuario)
        db.session.commit()
        return usuario.to_json(), 201
