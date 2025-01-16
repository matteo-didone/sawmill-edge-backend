# Gestione importazioni librerie
import asyncio

# Gestione importazioni da altre pagine del programma
from protocols.Opc_Ua import connection_to_server


# Funzione Principale
async def main():
    endpoint = "opc.tcp://127.0.0.1:4840/freeopcua/server/"   #Inserire stringa connessione corretta
    await connection_to_server(endpoint)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Chiusura in corso...")