from flask import Flask, request, jsonify
from services.pix_service import create_charge, pay_charge

app = Flask(__name__)

@app.route("/bank/pix/charges", methods=["POST"])
def create_pix_charge():
    data = request.get_json()
    return create_charge(data)

@app.route("/bank/pix/pay", methods=["POST"])
def pay_pix_charge():
    data = request.get_json()
    return pay_charge(data)

if __name__ == "__main__":
    app.run(port=6000, debug=True)
