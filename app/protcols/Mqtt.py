import paho.mqtt.client as mqtt
import json

class MacchinarioMQTT:
    def __init__(self, broker_address="localhost", broker_port=1883, topic_command="macchinario/comando", topic_status="macchinario/stato"):
        self.broker_address = broker_address
        self.broker_port = broker_port
        self.topic_command = topic_command
        self.topic_status = topic_status
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

    def arresta_macchinario(self):
        self.macchinario_attivo = False
        print("Macchinario arrestato")
        self.client.publish(self.topic_status, "arrestato")

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
        comando = msg_json.get("comando", "").strip().lower() # Estrai il comando dal JSON
        print(f"Comando ricevuto: {comando}")

        if comando == "avvia":
            self.avvia_macchinario()
        elif comando == "arresta":
            self.arresta_macchinario()
        else:
            print("Comando non riconosciuto")

    def avvia(self):
        try:
            self.client.connect(self.broker_address, self.broker_port, 60)
            print(f"Connesso al broker MQTT ({self.broker_address}:{self.broker_port})")
            self.client.loop_forever()
        except KeyboardInterrupt:
            print("Arresto del programma")
        except Exception as e:
            print(f"Errore durante la connessione al broker: {e}")
