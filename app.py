import flask
from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return flask.render_template('index.html')
@app.route('/events')
def events():
    return flask.render_template('events.html')
@app.route('/sign-in')
def sign_in():
    return flask.render_template('sign-in.html')
    
if __name__ == '__main__':
    app.run(debug=True)