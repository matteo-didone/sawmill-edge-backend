# Import da altri file del programma
from app.config.Node_Id import node_ids

# Import da librerie esterne
from asyncua import Client, ua


# Funzione per connettersi al server OPC-UA
async def connect_to_server(connection_url):
    try:
        client = Client(url=connection_url)
        await client.connect()
        print("Connesso al server OPC-UA")
        return client
    except Exception as e:
        print(f"Errore durante la connessione al server OPC-UA: {e}")
        return None

# Funzione per leggere i valori dei nodi
async def read_nodes(connection_url):

    valori_nodi = {}

    try:
        async with Client(url=connection_url) as client:
            print("Connesso al server OPC-UA per la lettura dei nodi")

            # Itera su tutti i nodi definiti in node_ids
            for key, node_id in node_ids.items():
                try:
                    # Ottieni il nodo e leggi il valore
                    nodo = client.get_node(node_id)
                    valore = await nodo.read_value()
                    valori_nodi[key] = valore
                    # Invio dei dati al Front-End tramite API
                    #await send_data_to_api(key, valore)
                except Exception as e:
                    print(f"Errore durante la lettura del nodo '{key}': {e}")
                    valori_nodi[key] = None

    except Exception as e:
        print(f"Errore generale durante la connessione al server OPC-UA: {e}")
    finally:
        print("Lettura dei nodi completata.")
        return valori_nodi

# Funzione per scrivere un valore in un nodo
async def write_to_node(connection_url, node_key, value):
    try:
        async with Client(url=connection_url) as client:
            print("Connesso al server OPC-UA per la scrittura")

            # Ottieni il nodo corrispondente
            node = client.get_node(node_ids[node_key])

            # Scrivi il valore nel nodo
            await node.write_value(value)
            print(f"Valore '{value}' scritto con successo nel nodo '{node_key}'")
    except Exception as e:
        print(f"Errore durante la scrittura sul nodo '{node_key}': {e}")
    finally:
        print("Scrittura completata.")

# Funzione principale per gestire connessione e lettura
async def main(connection_url):
    client = await connect_to_server(connection_url)
    if client:
        try:
            await read_nodes(client)
        finally:
            await client.disconnect()
            print("Disconnesso dal server OPC-UA.")


from asyncua import Client


async def method_get(connection_url, nodei, nodes,):
    async with Client(url=connection_url) as client:
        try:
            await client.nodes.objects.call_method(ua.NodeId(nodei, nodes))

        except Exception as e:
            print(f"Error starting machine: {e}")