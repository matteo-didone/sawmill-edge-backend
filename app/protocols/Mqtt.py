# Importazione librerie esterne
import json
import asyncio
import time
from threading import Thread

# Importazione pagine interne del progetto
import paho.mqtt.client as mqtt
from .Opc_Ua import write_to_node, read_nodes
from app.config.config import endpoint
from app.config.Node_Id import node_ids


class MacchinarioMQTT:
    def __init__(self, broker_address="localhost", broker_port=1883, topic_command="macchinario/comando",
                 topic_status="macchinario/stato"):
        self.broker_address = broker_address
        self.broker_port = broker_port
        self.topic_command = topic_command
        self.topic_status = topic_status
        self.topic_parameters = "macchinario/parametri"
        self.macchinario_attivo = False
        self.client = mqtt.Client()

        # Configura le callback
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def stato_macchinario(self):
        return self.macchinario_attivo

    def avvia_macchinario(self):
        self.macchinario_attivo = True
        print("Macchinario avviato")
        self.client.publish(self.topic_status, "avviato")
        asyncio.run(write_to_node(endpoint, "state", 1.0))

    def arresta_macchinario(self):
        self.macchinario_attivo = False
        print("Macchinario arrestato")
        self.client.publish(self.topic_status, "arrestato")
        asyncio.run(write_to_node(endpoint, "state", 0.0))  # Usa asyncio.run per chiamare write_to_node

    def invia_parametri(self):
        while True:
            if self.macchinario_attivo:
                parametri = {}
                for parametro, node_id in node_ids.items():
                    try:
                        # Leggi il valore del nodo OPC UA
                        valore = asyncio.run(read_nodes(endpoint))
                        parametri[parametro] = valore
                    except Exception as e:
                        print(f"Errore durante la lettura del nodo {parametro}: {e}")
                        parametri[parametro] = None

                # Pubblica i parametri sul broker MQTT
                self.client.publish(self.topic_parameters, json.dumps(parametri))
                print(f"Parametri inviati: {parametri}")

            time.sleep(1)  # Invia i parametri ogni secondo

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connesso al broker MQTT")
            self.client.subscribe(self.topic_command)
        else:
            print(f"Connessione fallita. Codice di errore: {rc}")

    def on_message(self, client, userdata, msg):
        # Decodifica il payload come stringa e carica il JSON
        payload_str = msg.payload.decode("utf-8")
        msg_json = json.loads(payload_str)  # Assicurati che il payload sia un JSON valido
        comando = msg_json.get("command", "").strip().lower()  # Estrai il comando dal JSON
        print(f"Comando ricevuto: {comando}")

        if comando == "avvia":
            self.avvia_macchinario()
        elif comando == "arresta":
            self.arresta_macchinario()
        else:
            print("Comando non riconosciuto")

    def avvia(self):
        try:
            # Avvia il thread per l'invio dei parametri
            parametro_thread = Thread(target=self.invia_parametri, daemon=True)
            parametro_thread.start()

            # Connessione al broker MQTT
            self.client.connect(self.broker_address, self.broker_port, 60)
            print(f"Connesso al broker MQTT ({self.broker_address}:{self.broker_port})")
            self.client.loop_forever()
        except KeyboardInterrupt:
            print("Arresto del programma")
        except Exception as e:
            print(f"Errore durante la connessione al broker: {e}")
