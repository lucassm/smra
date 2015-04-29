# -*- coding: utf-8 -*-

from pade.misc.common import start_loop
from pade.misc.utility import display_message
from pade.core.agent import Agent
from pade.acl.messages import ACLMessage
from pade.acl.aid import AID
from pade.behaviours.protocols import FipaRequestProtocol

import json

import iec61850

"""
    Este é o código do agente Agente Goose!

    Este agente tem por finalidade simular o envio de uma mensagem
    GOOSE para o agente Dispositivo, avisando que alguma proteção
    atuou e que por isso um religador foi comandado interropendo o
    fornecimento de energia no setor atingido pela falta e nos setores
    a jusante do setor afetado do mesmo alimentador.

    Este agente só tem funcionalidade de simulação e enquanto o sistema
    não capta a mensagem GOOSE diretamente do IED de proteção.
"""


"""

    Comportamentos
    ==============

    -> CompRequest1 : É o único comportamento deste e tem o objetivo
    de enviar uma mensagem ao agente Dispositivo

"""


class CompRequest1(FipaRequestProtocol):
    """
        Comportamento FIPA REQUEST
        ==========================

        Envia mensagem REQUEST ao agente Dispositivo
        e recebe uma mensagem INFORM de confimação
        de recebimento
    """
    def __init__(self, agent, message):
        super(CompRequest1, self).__init__(
            agent, message=message, is_initiator=True)

    def handle_inform(self, message):
        """
            Método handle_inform
            ====================

            Metodo recebe mensagem de confirmação do
            agente Dispositivo
        """
        content = json.loads(message.content)
        if content['ref'] == 'R_01':
            display_message(self.agent.aid.name, 'Mensagem INFORM Recebida')


class AgenteGoose(Agent):
    """
        Classe AgenteGoose
        ==================

        Classe que representa o agente Goose e seus
        comportamentos
    """
    def __init__(self, aid):

        super(AgenteGoose, self).__init__(aid=aid, debug=False)

        iec61850.createConnection('localhost', 5001)
        iec61850.operate('SEL_751_1PRO/BKR1CSWI1.Pos', False)
        iec61850.closeConnection()

        message = ACLMessage(ACLMessage.REQUEST)
        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_content(json.dumps({'ref': 'R_01',
                                        'dados': {'chaves': ['1'],
                                                  'estados': [0]
                                                  }
                                        }))
        message.add_receiver(AID('S1_AD1'))

        comprtamento_requisicao = CompRequest1(self, message)
        self.behaviours.append(comprtamento_requisicao)

if __name__ == '__main__':
    """
        script de teste
        ===============
    """

    agente_goose = AgenteGoose(AID('agente_goose'))

    agentes = [agente_goose]

    start_loop(agentes)
