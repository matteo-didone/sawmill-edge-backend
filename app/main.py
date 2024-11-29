import asyncio
from asyncua import Client

# Funzione di connessione al server OPC-UA in base all'url inserito
async def connectionToServer (connectionUrl):

    endpoint = connectionUrl

    # NodeId del nodo da leggere
    #node_id = {}

    node_id = "ns=2;i=1"

    #node_id["machine_state"] = "ns=2;i=1"  # Sostituisci con il NodeId corretto per il nodo "pieces"
    #node_id["active"] = "ns=2;i=1"  # Sostituisci con il NodeId corretto per il nodo "active"
    #node_id["working"] = "ns=2;i=1"  # Sostituisci con il NodeId corretto per il nodo "working"
    #node_id["stopped"] = "ns=2;i=1"  # Sostituisci con il NodeId corretto per il nodo "stopped"
    #node_id["alarm"] = "ns=2;i=1"  # Sostituisci con il NodeId corretto per il nodo "alarm"
    #node_id["error"] = "ns=2;i=1"  # Sostituisci con il NodeId corretto per il nodo "error"
    #node_id["cutting_speed"] = "ns=2;i=1"  # Sostituisci con il NodeId corretto per il nodo "cutting_speed"
    #node_id["power_drain"] = "ns=2;i=1"  # Sostituisci con il NodeId corretto per il nodo "power_drain"
    
    previous_value = None  # Per tenere traccia dell'ultimo valore letto
    
    try:
        async with Client(url=endpoint) as client:
            print("Connesso al server OPC-UA")
            
            node = client.get_node(node_id)
            
            while True:
                try:
                    # Legge il valore del nodo
                    value = await node.read_value()
                    
                    # Stampa solo se il valore è cambiato
                    if value != previous_value:
                        print(f"Valore aggiornato del nodo '{node_id}' (pieces): {value}")
                        previous_value = value
                
                except Exception as e:
                    print(f"Errore durante la lettura del nodo: {e}")
                
                # Attende un breve intervallo prima di leggere di nuovo
                await asyncio.sleep(1)
    
    except asyncio.CancelledError:
        print("Esecuzione interrotta dall'utente.")
    except Exception as e:
        print(f"Errore generico: {e}")
    finally:
        print("Programma terminato.")


# Funzione Principale
async def main():
    # Endpoint del server OPC-UA
    endpoint = "opc.tcp://192.168.100.53:4841/freeopcua/server/" 
    asyncio.run(connectionToServer(endpoint))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Chiusura in corso...")
