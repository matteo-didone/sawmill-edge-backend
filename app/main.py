# Importazione di librerie esterne
from multiprocessing import Process
import asyncio

# Importazione da file interni del programma
from protocols.Opc_Ua import connection_to_server
from app.protocols.Mqtt import MacchinarioMQTT
from app.config.config import endpoint

def avvia_mqtt(broker_address, broker_port, topic_command, topic_status):
    # Inizializza e avvia il client MQTT
    macchinario = MacchinarioMQTT(broker_address, broker_port, topic_command, topic_status)
    macchinario.avvia()  # Avvia il loop MQTT

# Funzione principale
async def main():
    broker_address = "localhost"  # Cambia se necessario
    broker_port = 1883
    topic_command = "macchinario/comando"
    topic_status = "macchinario/stato"

    # Avvia il processo per il gestore MQTT
    mqtt_process = Process(target=avvia_mqtt, args=(broker_address, broker_port, topic_command, topic_status))
    mqtt_process.start()

    # Esegui la connessione al server OPC UA
    await connection_to_server(endpoint)

    # Puoi decidere di terminare il processo MQTT al termine del programma principale
    mqtt_process.join()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Chiusura in corso...")
