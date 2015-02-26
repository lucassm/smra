from pade.misc.common import start_loop
from agente_alimentador import AgenteAlimentador
from pade.acl.aid import AID

if __name__ == '__main__':

    # Agentes Alimentadores
    aa_1 = AgenteAlimentador(AID('S2_AL1'))
    aa_1.ams({'name': '192.168.0.100', 'port': 8000})

    agentes = [aa_1]
    start_loop(agentes, gui=False)
