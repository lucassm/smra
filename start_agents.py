from pade.misc.common import set_ams, start_loop
from agente_alimentador import AgenteAlimentador
from agente_dispositivo import AgenteDispositivo
from agente_goose import AgenteGoose
from pade.acl.aid import AID

if __name__ == '__main__':
    set_ams('localhost', 8000, debug=False)

    # Agentes Alimentadores
    aa_1 = AgenteAlimentador(AID('S1_AL1'))
    aa_2 = AgenteAlimentador(AID('S1_AL2'))
    aa_3 = AgenteAlimentador(AID('S2_AL1'))

    # Agentes Dispositivo
    ad_1 = AgenteDispositivo(AID('S1_AD1'), aa_1)
    ad_2 = AgenteDispositivo(AID('S1_AD2'), aa_2)
    ad_3 = AgenteDispositivo(AID('S2_AD1'), aa_3)

    # Agentes Goose
    goose = AgenteGoose(AID('GOOSE_1'))

    agentes = [aa_1, aa_2, aa_3, ad_1, ad_2, ad_3, goose]
    start_loop(agentes, gui=True)
