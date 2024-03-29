from flask import Flask, render_template, redirect, flash
import os, time
from flask_mqtt import Mqtt
import json
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from flask_wtf import FlaskForm
from flask_login import login_user, current_user, login_required, LoginManager, logout_user
from wtforms.validators import DataRequired
from wtforms import StringField, PasswordField, SubmitField, IntegerField, validators


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
TOPICS = { 
    'set': 'project/esp32/appliances', 
    'status': 'project/esp32/appliances/status', 
    'readings': 'project/arduino/readings', 
    'ping_arduino': 'project/arduino/get',
    'set_wifi': 'project/wifi_details/set' 
    }
# mqtt.subscribe(TOPICS['status'])
status = {
    "window_mode": False
}
"""
readings will contain data from arduino iot33 node which 
consists of temperature, humidity, sensor label, timestamp etc
"""
readings = {}
# database
engine = create_engine('sqlite:///database.db.sqlite', echo=True, connect_args={'check_same_thread': False})
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

# appliance table 
class Appliance(base):
    __tablename__ = 'Appliances'
    
    id = Column(Integer, primary_key=True) 
    name = Column(String, unique=True, nullable=False) 
    power_rating = Column(Integer, unique=False, nullable=False)
    # last_status = Column(String) 

# Class representing a singleton object that will be used to track power usage throughout
class PowerUsage(base):
    __tablename__ = 'PowerUsage'
    id = Column(Integer, primary_key=True)
    power_usage = Column(Integer, default=0)
    power_threshold = Column(Integer, default=1000001)

# Class/Table for storing Wifi Settings to be sent to the microcontrollers for easy access
class WifiDetails(base):
    __tablename__ = 'WifiDetails'
    id = Column(Integer, primary_key=True, autoincrement=True)
    ssid = Column(String, unique=True, nullable=False)
    password = Column(String, unique=False, nullable=False)

# Wifi form
class WifiDetailsForm(FlaskForm):
    ssid = StringField('wifi id', validators=[DataRequired()])
    password = PasswordField('wifi password', validators=[DataRequired()]) 
    submit = SubmitField('Submit')

# Login Page form
class LoginForm(FlaskForm):
    username = StringField('username', validators=[DataRequired()])
    password = StringField('password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class PowerSettingsForm(FlaskForm):
    power_threshold = IntegerField('Max Power', validators=[DataRequired()])
    submit = SubmitField('Submit') 

'''
    Created a form for adding new appliances!
'''
class RegisterAppliance(FlaskForm):
    name = StringField('appliance name', validators=[DataRequired()])
    power_rating = IntegerField('appliance power rating', validators=[DataRequired()])
    submit = SubmitField('Submit')
    
'''
    A form to create new users
'''
class RegisterUser(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), validators.EqualTo('password_confirm', 'Passwords must match')])
    password_confirm = PasswordField('Confirm Password', validators=[DataRequired()])
    submit = SubmitField('Submit') 


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

# pre populate db first time
if not session.query(Appliance).filter(Appliance.name == 'led').all():
    session.add(Appliance(name='led', power_rating=5))
    session.commit()
else:
    print("led is already added!")

# create the power tracker object
if not session.query(PowerUsage).filter(PowerUsage.id == 1).first():
    session.add(PowerUsage(id=1))
    session.commit()

# create wifi details for the first time
if not session.query(WifiDetails).all():
    session.add(WifiDetails(ssid='None', password='None'))
    session.commit()

def broadcast_wifi_details():
    # set wifi details on all the microcontrollers
    wifi_details = session.query(WifiDetails).first()
    mqtt.publish(TOPICS['set_wifi'], payload=json.dumps({'ssid': wifi_details.ssid, 'password': wifi_details.password}))

def refresh_status():
    mqtt.publish(TOPICS['status'], payload=json.dumps({}))

@login_manager.user_loader
def user_loader(user_id):
    # return the corresponding User object to the user_id
    return session.query(User).filter(User.username == user_id).first()

# MQTT methods
@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    print("Connected to the broker")
    # for topic in TOPICS:
    # data from the esp32 
    client.subscribe(TOPICS['status'])
    # data from the arduino 
    client.subscribe(TOPICS['readings'])

@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    # update status data 
    if message.topic == TOPICS['status']:
        payload = json.loads(message.payload.decode())
        print("recieved from status topic")
        # print(payload)
        for key in payload:
            global status 
            status[key] = 'ON' if payload[key] == '1' else 'OFF'
        print(status)
    elif message.topic == TOPICS['readings']:
        payload = json.loads(message.payload.decode())
        global readings 
        readings = payload 
    # print("arduino readings recieved", payload)
    return redirect("/")

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
                # ping both esp32 and arduino to get the status of pins/appliances/readings etc
                print("publishing to status topic") 
                mqtt.publish(TOPICS['status'], payload=json.dumps({}))
                mqtt.publish(TOPICS['ping_arduino']) 
                # wait to get esp32's published data which is sent after esp32 processes above message 
                # just compensating for the delay
                time.sleep(0.5) 
                # redirect to the index page 
                return redirect('/')
        flash('Wrong username or password!')
    
    return render_template('login.html', form=form)

@app.route('/register_app', methods=['GET', 'POST'])
@login_required
def register_app():
    form = RegisterAppliance()    
    if form.validate_on_submit():
        new_app = session.query(Appliance).filter(Appliance.name == form.name.data).first()
        if new_app:
            flash('An appliance with the same name already exists!')
            return redirect('/register_app') 
        new_app = Appliance(name=form.name.data, power_rating=form.power_rating.data) 
        session.add(new_app)
        session.commit()
        flash(f"{form.name.data} was added!")
        return redirect('/') 
    
    return render_template('register_app.html', form=form)

@app.route('/user_dashboard')
@login_required
def user_dashboard():
    if not current_user.is_authenticated:
        return redirect('/user_dashboard') 
    
    return render_template('user_dashboard.html', users=session.query(User).all())

# register new users
@app.route('/register_user', methods=['GET', 'POST'])
@login_required
def register_user():
    form = RegisterUser()
    
    if form.validate_on_submit():
        new_user = session.query(User).filter(User.username == form.username.data).first()
        if new_user:
            flash('A user with the same username already exists!')
            return redirect('/register_app') 
        new_user = User(username=form.username.data, password=form.password.data) 
        session.add(new_user)
        session.commit()
        flash(f"{form.username.data} was added!")
        return redirect('/') 
    return render_template('register_user.html', form=form)

@app.route('/change_power_settings', methods=['GET', 'POST'])
@login_required
def change_power_settings():
    form = PowerSettingsForm()

    if form.validate_on_submit(): 
        old_settings = session.query(PowerUsage).filter(PowerUsage.id == 1).first()
        # change power threshold field of the object
        old_settings.power_threshold = form.power_threshold.data
        # print(old_settings)
        session.commit()
        CURRENT_POWER_USAGE = session.query(PowerUsage).filter(PowerUsage.id == 1).first().power_usage
        # repeated actions 
        POWER_USAGE_THRESHOLD = session.query(PowerUsage).filter(PowerUsage.id == 1).first().power_threshold 
        # print(CURRENT_POWER_USAGE) 
        if CURRENT_POWER_USAGE > POWER_USAGE_THRESHOLD:
            flash("POWER BUDGET EXCEEDED! PLEASE TURN OFF SOME APPLICATIONS")
            # publish to power exceeded topics so others can get notified 
        flash("Power settings updated")
        return redirect('/')
    
    # on GET request 
    old_settings = session.query(PowerUsage).filter(PowerUsage.id == 1).first()
    return render_template('power_settings_form.html', form=form, old_data=old_settings.power_threshold)

@app.route('/wifi_settings', methods=['GET', 'POST'])
@login_required
def wifi_settings():
    form = WifiDetailsForm() 

    if form.validate_on_submit():
        old_details = session.query(WifiDetails).first()
        old_details.ssid = form.ssid.data
        old_details.password = form.password.data
        session.commit()
        # set updated wifi details on all the microcontrollers
        broadcast_wifi_details()
        # wifi_details = session.query(WifiDetails).first()
        # mqtt.publish(TOPICS['set_wifi'], payload=json.dumps({'ssid': wifi_details.ssid, 'password': wifi_details.password}))        
        flash("Wifi settings updated") 
        return redirect('/')
    old_details = session.query(WifiDetails).first()
    # print(old_details)
    return render_template('wifi_settings.html', form=form, old_details=old_details)

'''
# DYNAMIC QUERY/FILTERING
# CURRENTLY IN DEVELOPMENT
@app.route('/delete/<table_name>/<identifier>')
@login_required
def delete_from_db(table_name, identifier):
    field = 'username' if table_name == 'User' else 'name'
    record = None
    query = "record = session.query(%s).filter(%s.%s == '%s').first()" % (table_name, table_name, field, identifier)
    exec(query, globals(), locals())
    # print("#"*20)
    # print(record)
    # print(query)
    # print("#"*20)
    session.delete(record)
    session.commit()
    flash(f"{identifier} was deleted!")
    return redirect('/')
'''

@app.route('/delete_app/<app_name>')
@login_required
def delete_app(app_name):
    app = session.query(Appliance).filter(Appliance.name == app_name).first()
    session.delete(app)
    session.commit()
    flash(f"{app_name} was deleted!")
    return redirect('/')

@app.route('/delete_user/<user_name>')
@login_required
def delete_user(user_name):
    user = session.query(User).filter(User.username == user_name).first()
    session.delete(user)
    session.commit()
    flash(f"{user_name} was deleted!")
    return redirect('/')

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
    # print(readings)
    refresh_status()
    print(readings)
    time.sleep(0.5)
    return render_template('index.html', apps=session.query(Appliance).all(), data=status, readings=readings, window_mode=status["window_mode"])

# changed the route to '/set/<appliance>/<int:act>'
# so now we can use the same view function for different appliances
@app.route('/set/<appliance>/<int:act>')
@login_required
def set_app(appliance, act):
    
    # publish a message on the set topic 
    # app = session.query(Appliance)
    if appliance == 'window':
        if act == 2:
            status["window_mode"] = not status["window_mode"]
        mqtt.publish(TOPICS['ping_arduino'], payload=json.dumps({appliance: act}))
    else:
        '''
            CHECK FOR POWER OVERLOAD HERE
        ''' 
        refresh_status()
        app_power_rating = session.query(Appliance).filter(Appliance.name == appliance).first().power_rating
        # if application was turned off then subtract the power rating otherwise add it
        CURRENT_POWER_USAGE = session.query(PowerUsage).filter(PowerUsage.id == 1).first().power_usage
        # repeated actions 
        if status[appliance] != act:
            CURRENT_POWER_USAGE = CURRENT_POWER_USAGE + (-app_power_rating if act == 0 else app_power_rating)  
        POWER_USAGE_THRESHOLD = session.query(PowerUsage).filter(PowerUsage.id == 1).first().power_threshold 
        # print(CURRENT_POWER_USAGE) 
        if CURRENT_POWER_USAGE > POWER_USAGE_THRESHOLD:
            flash("POWER BUDGET EXCEEDED! PLEASE TURN OFF SOME APPLICATIONS")
        mqtt.publish(TOPICS['set'], payload=json.dumps({appliance: act}))
    # wait to get esp32's published data which is sent after esp32 processes above message 
    # just compensating for the delay
    time.sleep(0.5) 
    # show_modal = True
    return redirect('/')

if __name__ == '__main__':
    # app.run(host="192.168.80.101", debug=True)
    app.run(host="192.168.80.101", debug=True)

