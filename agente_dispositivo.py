# -*- coding: utf-8 -*-

from pade.misc.common import start_loop
from pade.misc.utility import display_message
from pade.core.agent import Agent
from pade.acl.messages import ACLMessage
from pade.acl.aid import AID
from pade.behaviours.protocols import FipaRequestProtocol

import json
import numpy as np

#
# Comportamentos:
#
#   CompRequest_1 : Comportamento do tipo FIPA-Request Participante
#                   que o agente AD executa quando recebe uma
#                   mensagem GOOSE de um IED. Este comportamento identifica
#                   o setor sob falta e envia comando de abertura para os
#                   dispositivos de fronteira do setor faltoso;
#
#   CompRequest_3 : Comportamento do tipo FIPA-Request Iniciante que
#                   o agente AD executa ao enviar a mensagem que
#                   informa ao agente AA sobre a ocorrencia de uma
#                   falta no sistema;
#


class CompRequest1(FipaRequestProtocol):

    def __init__(self, agent):
        super(CompRequest1, self).__init__(
            agent=agent, message=None, is_initiator=False)

    def handle_request(self, message):

        # carrega o conteudo da mensagem recebida
        self.content = json.loads(message.content)

        if self.content['ref'] == 'R_01':
            display_message(self.agent.aid.name, 'Mensagem REQUEST recebida')

            resposta = message.create_reply()
            resposta.set_performative(ACLMessage.INFORM)
            resposta.set_content(json.dumps({'ref': 'R_01'}, indent=4))
            self.agent.send(resposta)

            # chaves_de_isolacao = self.encontrar_chaves_de_isolacao()

            # # # # # #
            # TODO: envia mensagem MMS para abrir as chaves de isolacao!
            # # # # # #

            message = ACLMessage(ACLMessage.REQUEST)
            message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
            message.set_content(json.dumps({'ref': 'R_04',
                                            'dados': {'chaves': ['1'],
                                                      'estados': [0]
                                                      }
                                            },
                                           indent=4)
                                )
            message.add_receiver(self.agent.agente_alimentador.aid.localname)

            # lança comportamento
            comp = CompRequest4(self.agent, message)
            self.agent.behaviours.append(comp)
            comp.on_start()

    def encontrar_setor_sob_falta(self):
        chave_nome = self.content['dados']['chaves'][0]
        chave = self.alimentador.chaves[str(chave_nome)]
        setor_1 = chave.n1
        setor_2 = chave.n2
        rnp = self.alimentador.rnp_dic()
        prof_1 = rnp[setor_1.nome]
        prof_2 = rnp[setor_2.nome]
        if prof_1 > prof_2:
            return setor_1.nome
        else:
            return setor_2.nome

    def encontrar_chaves_de_isolacao(self):
        setor_sob_falta = self.encontrar_setor_sob_falta()
        rnp = self.alimentador.rnp_dic()
        prof = rnp[setor_sob_falta]
        setores_adjacentes = list()
        for i in range(np.size(self.alimentador.rnp, axis=1)):
            if int(self.alimentador.rnp[0, i]) == (int(prof) + 1):
                setores_adjacentes.append(self.alimentador.rnp[1, i])

        chaves_de_isolacao = list()
        for chave in self.alimentador.chaves.values():
            if (chave.n1.nome or chave.n2.nome) == setor_sob_falta:
                chaves_de_isolacao.append(chave.nome)

        return chaves_de_isolacao


class CompRequest4(FipaRequestProtocol):

    def __init__(self, agent, message):
        super(CompRequest4, self).__init__(agent=agent,
                                           message=message,
                                           is_initiator=True)

    def handle_agree(self, message):

        # carrega conteudo da mensagem recebida
        self.content = json.loads(message.content)

        if self.content['ref'] == 'R_04':
            display_message(self.agent.aid.name, 'Mensagem AGREE recebida')

    def handle_inform(self, message):

        # carrega conteudo da mensagem recebida
        self.content = json.loads(message.content)

        if self.content['ref'] == 'R_04':
            display_message(self.agent.aid.name, 'Mensagem INFORM recebida')


class AgenteDispositivo(Agent):

    def __init__(self, aid, aa):
        super(AgenteDispositivo, self).__init__(aid=aid, debug=False)
        self.agente_alimentador = aa
        comp_request_1 = CompRequest1(self)
        self.behaviours.append(comp_request_1)

if __name__ == '__main__':
    ad_1 = AgenteDispositivo(AID(name='AD_1'))

    agents_list = list([ad_1])
    start_loop(agents_list)
