from flask import Flask, render_template, redirect, flash
import os, sys, time
from flask_mqtt import Mqtt
import json
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from flask_wtf import FlaskForm
from flask_login import login_user, current_user, login_required, LoginManager, logout_user
from wtforms.validators import DataRequired
from wtforms import StringField, PasswordField, SubmitField


app = Flask(__name__)
key = os.urandom(24)
app.config['SECRET_KEY'] = key
app.config['MQTT_CLIENT_ID'] = 'flask_webapp'
app.config['MQTT_BROKER_URL'] = '139.59.61.26'  
app.config['MQTT_BROKER_PORT'] = 1883  
app.config['MQTT_USERNAME'] = 'ahbar'
app.config['MQTT_PASSWORD'] = '1234'
app.config['MQTT_KEEPALIVE'] = 5  # set the time interval for sending a ping to the broker to 5 seconds
mqtt = Mqtt(app)
TOPICS = { 'set': 'project/esp32/appliances', 'status': 'project/esp32/appliances/status' }
# mqtt.subscribe(TOPICS['status'])
status = {}
# database
engine = create_engine('sqlite:///Users.db.sqlite', echo=True, connect_args={'check_same_thread': False})
base = declarative_base()
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# User table representation
class User(base):
    __tablename__ = 'User'

    username = Column(String, primary_key=True)
    password = Column(String, nullable=False)
    authenticated = Column(Boolean, default=False)
    
    def is_active(self):
        # always returns True since all user are active
        return True
    
    def get_id(self):
        return self.username

    def is_authenticated(self):
        return self.authenticated
    
    def is_anonymous(self):
        # always return False since none of the users are anonymous 
        return False


# Login Page form
class LoginForm(FlaskForm):
    username = StringField('username', validators=[DataRequired()])
    password = StringField('password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

'''
    Could create a registraion form too!
'''

base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()
if session.query(User).all():
    print('A user already exists!')
else:
    new_user = User(username='ahbar', password='12345678')
    session.add(new_user)
    session.commit()
    print("New user added!")


@login_manager.user_loader
def user_loader(user_id):
    # return the corresponding User object to the user_id
    return session.query(User).filter(User.username == user_id).first()


# MQTT methods
@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    print("Connected to the broker")
    # we only need to sub to the 'status' topic
    # for topic in TOPICS:
    client.subscribe(TOPICS['status'])

@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    # update status data 
    if message.topic == TOPICS['status']:
        payload = json.loads(message.payload.decode())
        # print('payload received', type(payload), payload)
        for key in payload:
            # print(key, payload[key])
            status[key] = 'ON' if payload[key] == '1' else 'OFF'
        
        # print(status) 
        return status


# APP ROUTES 
@app.route('/login', methods=['GET', 'POST'])
def login():
    # automatically handles GET and POST request
    # GET requests -> display the login form
    # POST requests -> authenticate 
    if current_user.is_authenticated:
        return redirect('/')
    
    # create a LoginForm object
    form = LoginForm()
    if form.validate_on_submit():
        user = session.query(User).filter(User.username == form.username.data).first()
        if user:
            if user.password == form.password.data:
                # update the record 
                user.authenticated = True
                # session.add(user) <- we don't need this line because query object is connected to session
                # commit the changes 
                session.commit()
                login_user(user, remember=True)
                # redirect to the index page 
                return redirect('/')
        flash('Wrong username or password!')
    
    return render_template('login.html', form=form)

@app.route('/logout', methods=['GET'])
@login_required
def logout():
    # Logout the current user
    user = current_user
    user.authenticated = False
    # session.add(user) <- commented out this line because of the same reason as above
    session.commit()
    logout_user()
    return redirect('/login')

@app.route('/')
@login_required
def index():
    # print(status)
    # do we need below two lines ?????? i dont think so
    if not current_user.is_authenticated:
        return redirect('/login') 
    return render_template('index.html', data=status)

# changed the route to '/set/<appliance>/<int:act>'
# so now we can use the same view function for different appliances
@app.route('/set/<appliance>/<act>')
@login_required
def set_app(appliance, act):
    # publish a message on the set topic 
    mqtt.publish(TOPICS['set'], payload=json.dumps({appliance: act}))
    # wait to get esp32's published data which is sent after esp32 processes above message 
    # just compensating for the delay
    time.sleep(0.5) 
    # show_modal = True
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
    
