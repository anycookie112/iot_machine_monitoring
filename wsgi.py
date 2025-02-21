from main_app import app

server = app.server


#run in terminal
#gunicorn wsgi:server --bind 0.0.0.0:8888