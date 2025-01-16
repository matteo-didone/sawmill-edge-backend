import asyncio
from asyncua import Client

# Funzione di connessione al server OPC-UA
async def connection_to_server(connection_url):
    endpoint = connection_url

    # Dizionario per mappare i nomi dei nodi ai rispettivi NodeId
    node_ids = {
        "state":                "ns=2;i=2",
        "material":             "ns=2;i=3",
        "dimension":            "ns=2;i=4",
        "cutting_speed":        "ns=2;i=5",
        "feed_rate":            "ns=2;i=6",
        # Performace Metrics Nodes
        "cut_pieces":           "ns=2;i=7",
        "efficiency":           "ns=2;i=8",
        "cutting_force":        "ns=2;i=9",
        # Motor Parameters Nodes
        "power_consumption":    "ns=2;i=10",
        "motor_temperature":    "ns=2;i=11",
        # Saw Parameters Nodes
        "saw_temperature":      "ns=2;i=12",
        "blade_wear":           "ns=2;i=13",
        # Coolant System Nodes
        "coolant_level":        "ns=2;i=14",
        "coolant_flow":         "ns=2;i=15",
        "coolant_temperature":  "ns=2;i=16",
        # Safety Nodes
        "safety_barrier":       "ns=2;i=17",
        "anomaly_active":       "ns=2;i=18",
        "anomaly_type":         "ns=2;i=19"
    }

    previous_values = {key: None for key in node_ids}

    try:
        async with Client(url=endpoint) as client:
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


# Funzione Principale
async def main():
    endpoint = endpoint = "opc.tcp://127.0.0.1:4840/freeopcua/server/"
    await connection_to_server(endpoint)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Chiusura in corso...")