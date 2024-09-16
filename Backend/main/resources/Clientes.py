from flask_restful import Resource, reqparse
from flask import request, jsonify
from .. import db
from main.models.Cliente import Cliente as ClienteModel
import datetime as dt
import requests
import json
from sqlalchemy.exc import OperationalError
import time
from datetime import datetime
from sqlalchemy import Table, MetaData, extract, cast, Date
import locale
import logging

# Configuración de locales para fechas en español
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.utf8')
except locale.Error:
    locale.setlocale(locale.LC_TIME, 'C')  # Usa el locale predeterminado si falla

# Definir el request parser para los datos de cliente
cliente_parser = reqparse.RequestParser()
cliente_parser.add_argument('cellphone', type=str, required=True, help="Cellphone is required")
cliente_parser.add_argument('name', type=str, required=True, help="Name is required")
cliente_parser.add_argument('date', type=str, required=True, help="Date is required")
cliente_parser.add_argument('time', type=str, required=True, help="Time is required")
cliente_parser.add_argument('services', type=str, required=True, help="Services is required")

# Decorador para reintentar en caso de errores operacionales
def retry(func):
    def wrapper(*args, **kwargs):
        retries = 3
        for attempt in range(retries):
            try:
                return func(*args, **kwargs)
            except OperationalError:
                db.session.rollback()
                time.sleep(2 ** attempt)  # Exponential backoff
        return jsonify({"error": "Database connection lost. Please try again later."}), 500
    return wrapper

# Función para obtener la tabla de clientes dinámica basada en el username
def get_cliente_table(username):
    """Devuelve la tabla de clientes para el usuario específico."""
    table_name = f"clientes_{username}"
    metadata = MetaData(bind=db.engine)
    cliente_table = Table(table_name, metadata, autoload=True)
    return cliente_table

# Recurso para manejar operaciones sobre un solo cliente (GET, PUT, DELETE)
class Cliente(Resource):
    @retry
    def get(self, username, id):
        cliente_table = get_cliente_table(username)
        cliente = db.session.query(cliente_table).filter_by(id=id).first()
        if cliente:
            return dict(cliente), 200
        else:
            return {"message": "Cliente no encontrado"}, 404
    
    @retry
    def delete(self, username, id):
        cliente_table = get_cliente_table(username)
        cliente = db.session.query(cliente_table).filter_by(id=id).first()
        if cliente:
            db.session.delete(cliente)
            db.session.commit()
            return '', 204
        else:
            return {"message": "Cliente no encontrado"}, 404
    
    @retry
    def put(self, username, id):
        cliente_table = get_cliente_table(username)
        cliente = db.session.query(cliente_table).filter_by(id=id).first()
        if not cliente:
            return {"message": "Cliente no encontrado"}, 404

        args = cliente_parser.parse_args()
        try:
            date = dt.datetime.fromisoformat(args['date'])
            time = dt.datetime.strptime(args['time'], "%H:%M:%S").time()
            cliente.name = args['name']
            cliente.cellphone = args['cellphone']
            cliente.date = date
            cliente.time = time
            cliente.days_for_appointment = (date.date() - cliente.register_date.date()).days
            db.session.commit()
            return dict(cliente), 201
        except (ValueError, TypeError) as e:
            return {'error': str(e)}, 400

# Recurso para manejar operaciones sobre la lista de clientes (GET, POST)
class Clientes(Resource):
    
    @retry
    def get(self, username):
        # Obtener el parámetro de fecha de la URL
        fecha = request.args.get('fecha')
        nextdays = request.args.get('nextdays')

        if fecha or nextdays:
            # Si hay un parámetro de fecha o nextdays, ejecutamos la lógica de slots
            return self.get_available_slots(username)
        else:
            # Si no hay fecha, devolvemos todos los clientes
            cliente_table = get_cliente_table(username)
            clientes = db.session.query(cliente_table).all()
            return [dict(cliente) for cliente in clientes], 200
    
    @retry
    def post(self, username):
        args = cliente_parser.parse_args()
        cliente_table = get_cliente_table(username)
        try:
            # Crear un nuevo cliente en la tabla personalizada
            insert_query = cliente_table.insert().values(
                cellphone=args['cellphone'],
                name=args['name'],
                date=dt.datetime.fromisoformat(args['date']),
                time=dt.datetime.strptime(args['time'], "%H:%M:%S").time(),
                services=args['services'],
                register_date=dt.datetime.utcnow(),
                days_for_appointment=0
            )
            db.session.execute(insert_query)
            db.session.commit()
            return {"message": "Cliente agregado"}, 201
        except Exception as e:
            return {'error': str(e)}, 400
    
    @retry
    def get_available_slots(self, username):
        # Obtener el parámetro de fecha de la URL
        nextdays = request.args.get('nextdays')
        fecha = request.args.get('fecha')

        if fecha:
            try:
                # Convertir el timestamp de milisegundos a segundos
                timestamp = int(fecha) / 1000
                fecha_formateada = dt.datetime.fromtimestamp(timestamp).date()
                
            except ValueError:
                return {"message": "El formato de la fecha no es válido. Usa un timestamp válido"}, 400
            
            # Definir el conjunto de horas del día en formato de 24 horas con segundos (HH:MM:SS)
            horas_totales = [
                "09:00:00", "10:00:00", "11:00:00", "12:00:00", "13:00:00",
                "14:00:00", "15:00:00", "16:00:00", "17:00:00", "18:00:00"
            ]

            # Consulta para buscar citas que coincidan con la fecha proporcionada
            cliente_table = get_cliente_table(username)
            clientes = db.session.query(cliente_table).filter(
                cliente_table.c.date == fecha_formateada  # Comparación directa con la fecha
            ).all()

            if not clientes:
                # Si no hay citas registradas, todas las horas están disponibles
                slots_disponibles = [
                    {
                        "id": hora,  # El ID ya está en formato de 24 horas con segundos
                        "title": dt.datetime.strptime(hora, "%H:%M:%S").strftime("%I:%M %p")  # Convertir a formato 12 horas
                        
                    } for hora in horas_totales
                ]
                return {"fecha": str(fecha_formateada.strftime("%d-%m-%Y")), "slots": slots_disponibles}, 200

            # Extraer las horas ocupadas de los clientes encontrados y formatearlas en formato de 24 horas con segundos
            horas_ocupadas = [cliente.time.strftime("%H:%M:%S") for cliente in clientes]

            # Comparar y determinar las horas disponibles restando las horas ocupadas de las horas totales
            horas_disponibles = [hora for hora in horas_totales if hora not in horas_ocupadas]

            # Crear la estructura de 'slots' con id en formato de 24 horas con segundos y title en formato AM/PM
            slots_disponibles = [
                {
                    "id": hora,  # Mantener el ID en formato de 24 horas con segundos
                    "title": dt.datetime.strptime(hora, "%H:%M:%S").strftime("%I:%M %p")  # Convertir a formato AM/PM
                } for hora in horas_disponibles
            ]

            # Retornar las horas disponibles
            return {"fecha": str(fecha_formateada.strftime("%d-%m-%Y")), "slots": slots_disponibles}, 200
        elif nextdays:
            try:
                # Obtener la fecha actual
                fecha_actual = dt.datetime.now().date()

                # Definir las horas del día de trabajo (por ejemplo, 9:00 AM a 6:00 PM)
                horas_totales = [
                    "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM",
                    "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM"
                ]

                # Consulta para obtener las fechas con citas a partir del día de hoy
                cliente_table = get_cliente_table(username)
                citas_proximas = db.session.query(cast(cliente_table.c.date, Date)).filter(
                    cast(cliente_table.c.date, Date) >= fecha_actual
                ).group_by(cast(cliente_table.c.date, Date)).order_by(cast(cliente_table.c.date, Date)).all()

                # Lista para almacenar los días con citas disponibles
                dias_disponibles = []
                count_dias_disponibles = 0  # Contador de días disponibles encontrados

                # Revisar las fechas encontradas
                for cita in citas_proximas:
                    # Obtener las horas ocupadas para este día
                    horas_ocupadas = db.session.query(cliente_table.c.time).filter(
                        cast(cliente_table.c.date, Date) == cita[0]
                    ).all()

                    # Convertir las horas ocupadas a un formato legible (ejemplo: "09:00 AM")
                    horas_ocupadas_formato = [hora[0].strftime("%I:%M %p") for hora in horas_ocupadas]

                    # Determinar las horas disponibles para este día
                    horas_disponibles = [hora for hora in horas_totales if hora not in horas_ocupadas_formato]

                    # Si hay al menos una hora disponible, agregamos este día a la lista
                    if horas_disponibles:
                        # Convertir cita[0] (que es date) a datetime para poder usar timestamp()
                        cita_datetime = dt.datetime.combine(cita[0], dt.datetime.min.time())

                        # Formato de la fecha con el día de la semana abreviado y el mes abreviado en español
                        fecha_formateada = cita[0].strftime("%a %d de %b").capitalize()

                        dias_disponibles.append({
                            "id": int(cita_datetime.timestamp() * 1000),  # El ID en milisegundos
                            "fecha": fecha_formateada,  # Fecha en formato "Lun. 01 de sep."
                            "horas_disponibles": horas_disponibles
                        })
                        count_dias_disponibles += 1

                    # Si ya tenemos tres días disponibles, salimos del bucle
                    if count_dias_disponibles >= 3:
                        break

                # Si no hay suficientes días con citas disponibles, llenar con días vacíos
                while count_dias_disponibles < 3:
                    fecha_proxima = fecha_actual + dt.timedelta(days=count_dias_disponibles)
                    # Convertir fecha_proxima a datetime para usar timestamp()
                    fecha_proxima_datetime = dt.datetime.combine(fecha_proxima, dt.datetime.min.time())
                    fecha_formateada = fecha_proxima.strftime("%a %d de %b").capitalize()

                    dias_disponibles.append({
                        "id": int(fecha_proxima_datetime.timestamp() * 1000),  # El ID en milisegundos
                        "fecha": fecha_formateada,  # Fecha en formato "Lun. 01 de sep."
                        "horas_disponibles": horas_totales
                    })
                    count_dias_disponibles += 1

                # Retornar los días con citas disponibles (hasta un máximo de 3)
                return {
                    "message": "Días con citas disponibles",
                    "dias_disponibles": dias_disponibles[:3]  # Limitamos a 3 días
                }

            except Exception as e:
                return {"message": f"Error al procesar la solicitud: {str(e)}"}, 500
        else:
            # Si no se pasa la fecha, devolver todos los clientes
            cliente_table = get_cliente_table(username)
            clientes = db.session.query(cliente_table).all()
            return [dict(cliente) for cliente in clientes]
