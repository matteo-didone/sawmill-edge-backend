from flask import Blueprint, request, jsonify

# Creazione di un Blueprint per gestire i percorsi relativi alla macchina
machine_bp = Blueprint("machine", __name__)

# Stato della macchina
machine_state = {
    "status": "stopped",  # Stato iniziale
    "speed": 0
}


@machine_bp.route("/machine/start", methods=["POST"])
def start_machine():
    """
    Avvia la macchina con i parametri forniti.
    """
    data = request.json  # Ottiene i dati JSON dal corpo della richiesta
    speed = data.get("speed", 100)  # Valore predefinito per la velocità

    machine_state["status"] = "running"
    machine_state["speed"] = speed

    return jsonify({"message": "Macchina avviata", "state": machine_state})


@machine_bp.route("/machine/stop", methods=["POST"])
def stop_machine():
    """
    Arresta la macchina.
    """
    machine_state["status"] = "stopped"
    machine_state["speed"] = 0

    return jsonify({"message": "Macchina arrestata", "state": machine_state})


@machine_bp.route("/machine/status", methods=["GET"])
def get_machine_status():
    """
    Restituisce lo stato corrente della macchina.
    """
    return jsonify({"state": machine_state})
