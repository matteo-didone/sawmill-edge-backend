import asyncio
from asyncua import Client
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Modello per rappresentare i comandi
class Command(BaseModel):
    action: str  # "start" o "stop"

# Variabili globali
connection_task = None
opc_client = None
machine_node = None

async def connection_to_server(connection_url):
    global opc_client, machine_node

    endpoint = connection_url
    node_id = "ns=2;i=1"  # NodeId del nodo macchina (esempio)

    try:
        opc_client = Client(url=endpoint)
        await opc_client.connect()
        print("Connesso al server OPC-UA")

        machine_node = opc_client.get_node(node_id)

        # Monitoraggio dello stato macchina
        while True:
            try:
                value = await machine_node.read_value()
                print(f"Valore aggiornato del nodo '{node_id}': {value}")
            except Exception as e:
                print(f"Errore durante la lettura del nodo: {e}")

            await asyncio.sleep(1)

    except asyncio.CancelledError:
        print("Esecuzione interrotta.")
    except Exception as e:
        print(f"Errore generico: {e}")
    finally:
        if opc_client:
            await opc_client.disconnect()
            print("Disconnesso dal server OPC-UA")

@app.get("startup")
async def startup_event():
    global connection_task
    connection_url = "opc.tcp://192.168.100.53:4841/freeopcua/server/"  # Modifica con il tuo endpoint
    connection_task = asyncio.create_task(connection_to_server(connection_url))

@app.get("shutdown")
async def shutdown_event():
    global connection_task
    if connection_task:
        connection_task.cancel()
        await connection_task

@app.post("/command")
async def send_command(command: Command):
    global machine_node

    if not machine_node:
        return {"error": "Nodo macchina non connesso"}

    try:
        if command.action == "start":
            await machine_node.write_value(True)  # Scrive "True" per accendere
            return {"status": "Machine started"}
        elif command.action == "stop":
            await machine_node.write_value(False)  # Scrive "False" per spegnere
            return {"status": "Machine stopped"}
        else:
            return {"error": "Comando non riconosciuto"}
    except Exception as e:
        return {"error": f"Errore durante l'invio del comando: {e}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8400)
