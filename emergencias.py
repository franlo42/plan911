from pyhop import (Goal, State, declare_methods, declare_operators,
                   print_operators, pyhop)
from math import sqrt

TREATMENT_THRESHOLD = 8

#-------------------------------------------------------------------------------
# Clase del Estado
class EmergencyState(State):
    def __init__(self, name, ambulances, victims, hospitals, coordinates):
        super().__init__(name)
        self.ambulances = ambulances
        self.victims = victims
        self.hospitals = hospitals
        self.coordinates = coordinates

#----------------------------------------------------------------------------------------
# Helpers
def distance(c1, c2):
    x = pow(c1['X'] - c2['X'], 2)
    y = pow(c1['Y'] - c2['Y'], 2)
    return sqrt(x + y)

def choose_hospital(state, victim):
    """
        Devuelve el hospital más cercano a la víctima
        pasada por parámetros
    """
    victim_loc = state.victims[victim]["location"]
    if victim_loc not in state.coordinates:
        return None
    victim_coords = state.coordinates[victim_loc]
    best_distance = float("inf")
    best_hosp = None
    for hosp, info in state.hospitals.items():
        hosp_loc = info["location"]
        if hosp_loc not in state.coordinates:
            continue
        # Si la victima ya está en un hospital
        if hosp_loc == victim_loc:
            return None

        hosp_coords = state.coordinates[hosp_loc]
        d = distance(victim_coords, hosp_coords)
        if d < best_distance:
            best_distance = d
            best_hosp = hosp
    return best_hosp

#----------------------------------------------------------------------------------------
# Operadores
def drive_ambulance(state, ambulance, destination):
    if ambulance not in state.ambulances:
        return False

    state.ambulances[ambulance]["location"] = destination
    return state


def load_victim(state, victim, ambulance):
    amb_loc = state.ambulances[ambulance]["location"]
    vic_loc = state.victims[victim]["location"]
    if amb_loc != vic_loc:
        return False
    if state.ambulances[ambulance]['max_severity'] < state.victims[victim]['severity']:
        return False

    state.victims[victim]["in_ambulance"] = ambulance
    state.ambulances[ambulance]["victim"] = victim
    return state


def treat_victim_in_situ(state, victim):
    if victim not in state.victims:
        return False

    victim_info = state.victims[victim]

    if victim_info["severity"] < TREATMENT_THRESHOLD:
        return False

    if victim_info.get("treated", False):
        return False

    victim_info["treated"] = True
    return state


def drive_to_hospital(state, ambulance, hospital):
    if ambulance not in state.ambulances:
        return False
    if hospital not in state.hospitals:
        return False
    if state.ambulances[ambulance].get("victim", "") == "":
        return False

    current_loc = state.ambulances[ambulance]["location"]
    hospital_loc = state.hospitals[hospital]["location"]

    if current_loc == hospital_loc:
        return state

    state.ambulances[ambulance]["location"] = hospital_loc
    return state


def unload_victim(state, victim, hospital, ambulance):
    hospital_loc = state.hospitals[hospital]["location"]
    amb_loc = state.ambulances[ambulance]["location"]
    if hospital_loc != amb_loc:
        return False
    if state.victims[victim]["in_ambulance"] != ambulance:
        return False

    state.victims[victim]["location"] = hospital_loc
    state.victims[victim]["in_ambulance"] = None
    return state


declare_operators(
    drive_ambulance, load_victim, treat_victim_in_situ, drive_to_hospital, unload_victim
)
print_operators()

#------------------------------------------------------------------------------------------------------------
# métodos
def deliver_victim(state, victim, hospital):
    """
    Tarea de alto nivel para entregar a una víctima en un hospital.
    Se descompone en:
      1. select_ambulance: asigna (o trae) una ambulancia para la víctima.
      2. add_treatment: aplica tratamiento in situ si es necesario.
      3. transport_victim: carga a la víctima, conduce la ambulancia al hospital y descarga.
    """
    return [('select_ambulance', victim),
            ('add_treatment', victim),
            ('transport_victim', victim, hospital)]

declare_methods("deliver_victim", deliver_victim)

def select_ambulance_on_site(state, victim):
    """
    Método para 'select_ambulance' cuando ya existe una ambulancia en la localización
    de la víctima que pueda atender su nivel de gravedad.
    Asigna la ambulancia a la víctima (guardándola en state.victims[victim]['ambulance']).
    """
    victim_info = state.victims[victim]
    victim_loc = victim_info["location"]
    for amb in state.ambulances:
        if state.ambulances[amb]["location"] == victim_loc and \
           state.ambulances[amb]["max_severity"] >= victim_info["severity"]:
            state.victims[victim]['ambulance'] = amb
            return []  # No se requiere acción adicional
    return False  # Este método no se aplica si no hay ambulancia en sitio

def select_ambulance_from_elsewhere(state, victim):
    """
    Método para 'select_ambulance' cuando no hay ambulancia en la localización de la víctima.
    Busca la ambulancia más cercana (y que pueda atender la severidad) y genera la tarea
    para traerla hasta el lugar del accidente.
    """
    victim_info = state.victims[victim]
    victim_loc = victim_info["location"]
    victim_coords = state.coordinates[victim_loc]
    candidate = None
    best_distance = float("inf")
    for amb, info in state.ambulances.items():
        if info["max_severity"] < victim_info["severity"]:
            continue
        amb_coords = state.coordinates[info["location"]]
        d = distance(amb_coords, victim_coords)
        if d < best_distance:
            best_distance = d
            candidate = amb
    if candidate is None:
        return False  # No hay ambulancia adecuada
    state.victims[victim]['ambulance'] = candidate
    return [('drive_ambulance', candidate, victim_loc)]

declare_methods('select_ambulance', select_ambulance_on_site, select_ambulance_from_elsewhere)


def add_treatment_if_needed(state, victim):
    """
    Si la víctima requiere tratamiento in situ (por ejemplo, si su severidad supera un umbral)
    y aún no ha sido tratada, añade la tarea para tratarla.
    """
    victim_info = state.victims[victim]
    if victim_info["severity"] > TREATMENT_THRESHOLD and not victim_info.get("treated", False):
        return [('treat_victim_in_situ', victim)]
    return []

declare_methods('add_treatment', add_treatment_if_needed)

def transport_victim_method(state, victim, hospital):
    """
    Método para transportar a la víctima: cargarla en la ambulancia asignada,
    conducir la ambulancia hasta el hospital y descargarla.
    Se asume que en state.victims[victim]['ambulance'] se ha asignado la ambulancia.
    """
    amb = state.victims[victim].get("ambulance")
    if amb is None:
        return False
    return [('load_victim', victim, amb),
            ('drive_to_hospital', amb, hospital),
            ('unload_victim', victim, hospital, amb)]

declare_methods('transport_victim', transport_victim_method)



#--- Ampliación 2: Atención a todas las víctimas ---

# Tarea "deliver_victim" para cada víctima.
def deliver_all_victims(state):
    tasks = []
    for victim in state.victims.keys():
        hospital = choose_hospital(state, victim)
        if hospital is None:
            # Si no se encuentra hospital, se puede optar por abortar o simplemente omitir la víctima.
            continue
        tasks.append(("deliver_victim", victim, hospital))
    return tasks

declare_methods("deliver_all_victims", deliver_all_victims)
#-------------------------------------------------------------------------------------------------
ambulances = {
    "Amb1": {"location": "Hospital General", "max_severity": 10},
    "Amb2": {"location": "Ciudad de las Artes y las Ciencias", "max_severity": 5},
    "Amb3": {"location": "Hospital La Fe", "max_severity": 8},
}

victims = {
    "Victim1": {
        "name": "Pablo Motos",
        "age": 50, 
        "location": "Paiporta", 
        "severity": 7, 
        "treated": False
    },
    "Victim2": {
        "name": "Rita Barbará",
        "age": 60,
        "location": "Ciudad de las Artes y las Ciencias",
        "severity": 4,
        "treated": False,
    },
        "Victim3": {
        "name": "Camilo Sesto",
        "age": 70,
        "location": "Colón",
        "severity": 9,
        "treated": False,
    }
}

hospitals = {
    "Hospital1": {"name":"Hospital Clínic","location": "Hospital Clínic"},
    "Hospital2": {"name":"Hospital General","location": "Hospital General"},
    "Hospital3": {"name":"Hospital La Fe","location": "Hospital La Fe"},
}

coordinates = {
    "UPV": {"X": 28, "Y": 92},
    "Ciudad de las Artes y las Ciencias": {"X": 27, "Y": 93},
    "Colón": {"X": 26, "Y": 95},
    "Manises": {"X": 17.3, "Y": 86},
    "Paiporta": {"X": 21.4 , "Y": 80},
    "Hospital La Fe": {"X": 26, "Y": 88},
    "Hospital Clínic": {"X": 28, "Y": 90},
    "Hospital General": {"X": 22.4, "Y": 95},
}


state0 = EmergencyState("estado_emergencia", ambulances, victims, hospitals, coordinates)

goal1 = Goal("goal1")
goal1.hospital = "Hospital2"
goal1.victim = "Victim1"

# pyhop(state0, [("deliver_victim", goal1.victim, goal1.hospital)], verbose=3)

# Segunda ampliación: enviar todas las víctimas al hospital
pyhop(state0,[("deliver_all_victims",)], verbose=2)
