from .. import db
import base64

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)
    active = db.Column(db.Boolean, default=True)
    imagen = db.Column(db.String(255))  # Almacenar la URL de la imagen
    workdays = db.Column(db.String(255), nullable=False)
    workingHours = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Usuario {self.username}>"
    
    def to_json(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "password": self.password,
            "active": self.active,
            "imagen": self.imagen,  # Devolver la URL de la imagen
            "workdays": self.workdays,
            "workingHours": self.workingHours
        }
    
    @staticmethod
    def from_json(usuario_json):
        try:
            username = usuario_json.get("username")
            email = usuario_json.get("email")
            password = usuario_json.get("password")
            active = usuario_json.get("active")
            imagen = usuario_json.get("imagen")  # Aquí se guarda la URL de la imagen
            workdays = usuario_json.get("workdays")
            workingHours = usuario_json.get("workingHours")
            
            return Usuario(username=username, email=email, password=password, active=active, imagen=imagen, workdays=workdays, workingHours=workingHours)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Error al convertir JSON a Usuario: {e}")
