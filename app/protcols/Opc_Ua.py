#import da altri file del programma
from app.config.Node_Id import node_ids

#import da librerie esterne
from asyncua import Client
import asyncio

# Funzione di connessione al server OPC-UA
async def connection_to_server(connection_url):




    previous_values = {key: None for key in node_ids}

    try:
        async with Client(url=connection_url) as client:
            print("Connesso al server OPC-UA")

            # Ottieni i nodi
            nodes = {key: client.get_node(node_id) for key, node_id in node_ids.items()}

            while True:
                for key, node in nodes.items():
                    try:
                        # Leggi il valore del nodo
                        value = await node.read_value()

                        # Stampa solo se il valore è cambiato
                        if value != previous_values[key]:
                            print(f"Valore aggiornato del nodo '{key}': {value}")
                            previous_values[key] = value

                    except Exception as e:
                        print(f"Errore durante la lettura del nodo '{key}': {e}")

                # Attende 1 secondo prima di rileggere
                await asyncio.sleep(1)

    except asyncio.CancelledError:
        print("Esecuzione interrotta dall'utente.")
    except Exception as e:
        print(f"Errore generico: {e}")
    finally:
        print("Programma terminato.")