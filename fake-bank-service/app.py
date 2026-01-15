from flask import Flask
from routes.pix import pix_bp

app = Flask(__name__)
app.register_blueprint(pix_bp)

if __name__ == "__main__":
    app.run(port=6000, debug=True)

