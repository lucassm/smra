from pade.misc.common import start_loop
from agente_alimentador import AgenteAlimentador
from agente_dispositivo import AgenteDispositivo
from agente_goose import AgenteGoose
from pade.acl.aid import AID

if __name__ == '__main__':

    # Agentes Alimentadores
    aa_1 = AgenteAlimentador(AID('S1_AL1'))

    # Agentes Dispositivo
    ad_1 = AgenteDispositivo(AID('S1_AD1'), aa_1)

    # Agentes Goose
    # goose = AgenteGoose(AID('GOOSE_1'))

    # agentes = [aa_1, ad_1, goose]
    agentes = [aa_1, ad_1]
    start_loop(agentes, gui=False)
