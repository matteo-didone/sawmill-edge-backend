'''
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
'''

node_ids = {
    "state":                "ns=3;i=1007",
    "cutting_speed":        "ns=3;i=1003",
    "cut_pieces":           "ns=3;i=1001",
    "power_consumption":    "ns=3;i=1004"
}