import requests

# Base URL dell'API
API_BASE_URL = "http://localhost:8000/api/v1"

# Mappatura dei nodi agli endpoint API
NODE_ENDPOINT_MAP = {
    # Stato della macchina
    "state": "/status/state",
    "safety_barrier": "/status/safety_barrier",
    "anomaly_active": "/status/anomaly",
    "anomaly_type": "/status/anomaly",

    # Metriche di performance
    "cut_pieces": "/metrics/performance/cut_pieces",
    "efficiency": "/metrics/performance/efficiency",
    "cutting_force": "/metrics/performance/cutting_force",

    # Parametri del motore
    "power_consumption": "/metrics/motor/power_consumption",
    "motor_temperature": "/metrics/motor/temperature",

    # Parametri della sega
    "saw_temperature": "/metrics/saw/temperature",
    "blade_wear": "/metrics/saw/blade_wear",

    # Sistema di raffreddamento
    "coolant_level": "/metrics/coolant/level",
    "coolant_flow": "/metrics/coolant/flow",
    "coolant_temperature": "/metrics/coolant/temperature",
}

# Funzione per l'invio dei dati al corretto endpoint API in base al nodo OPC-UA
async def send_data_to_api(node_name, value):
    # Verifico se il nodo è mappato ad un endpoint
    if node_name not in NODE_ENDPOINT_MAP:
        print(f"Nodo '{node_name}' non riconosciuto. Nessun endpoint definito.")
        return

    # Costruisco l'URL di destinazione
    url = API_BASE_URL + NODE_ENDPOINT_MAP[node_name]

    # Costruisco il payload
    payload = {"value": value}

    try:
        # Invio dati tramite POST
        response = requests.post(url, json=payload, timeout=5)

        # Verifico la risposta
        if response.status_code == 200:
            print(f"Dato inviato a {url}: {payload}")
        else:
            print(f"Errore nell'invio a {url}: {response.status_code} - {response.text}")

    except requests.RequestException as e:
        print(f"Errore di connessione a {url}: {e}")