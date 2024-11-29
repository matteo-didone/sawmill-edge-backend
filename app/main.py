import asyncio
from asyncua import Client

async def main():
    # Endpoint del server OPC-UA
    endpoint = "opc.tcp://192.168.100.53:4841/freeopcua/server/"
    
    # NodeId del nodo da leggere
    node_id = "ns=2;i=1"  # Sostituisci con il NodeId corretto per il nodo "pieces"
    
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

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Chiusura in corso...")  # Gestisce CTRL+C