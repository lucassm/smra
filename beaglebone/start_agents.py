from pade.misc.common import start_loop
from agente_alimentador import AgenteAlimentador
from agente_dispositivo import AgenteDispositivo
from pade.acl.aid import AID

if __name__ == '__main__':

    # Agentes Alimentadores
    aa_1 = AgenteAlimentador(AID('S2_AL1@192.168.24.102:4001'))
    aa_1.ams = {'name': '192.168.24.101', 'port': 8000}

    # Agentes Dispositivos
    ad_1 = AgenteDispositivo(AID('S2_AD1@192.168.24.102:4002'), aa_1)
    ad_1.ams = {'name': '192.168.24.101', 'port': 8000}

    agentes = [aa_1, ad_1]
    start_loop(agentes, gui=False)
