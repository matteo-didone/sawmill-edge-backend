#import da altri file del programma
from app.config.Node_Id import node_ids

# Import di librerie esterne
import requests
import asyncio

async def send_data_to_api(node_name, value, url):
    payload = {
        "node": node_name,
        "value": value
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"Dato inviato con successo: {payload}")
        else:
            print(f"Errore nell'invio del dato {payload}: {response.status_code}")
    except requests.RequestException as e:
        print(f"Errore di connessione all'API: {e}")

