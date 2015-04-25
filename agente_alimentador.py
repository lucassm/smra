# -*- coding: utf-8 -*-
from pade.misc.common import start_loop
from pade.misc.utility import display_message
from pade.core.agent import Agent
from pade.acl.messages import ACLMessage
from pade.acl.aid import AID
from pade.behaviours.protocols import FipaRequestProtocol
from pade.behaviours.protocols import FipaContractNetProtocol
from xml2objects import carregar_topologia

from rede import Fasor

import json
import pickle

import numpy as np

#
# Comportamentos:
#
# CompRequest1 : Comportamento do tipo FIPA-Request Participante
#                que o agente AA executa quando recebe mensagem
#                do Agente AD com informações de TRIP no sistema
#                Este comportamento também lança o comportamento
#                ContractNet Iniciante, realiza a poda dos setores
#                desenergizados e envia mensagem de atualização da
#                topologia da rede para outros AA
#
# CompRequest2 : Comportamento do tipo FIPA-Request Participante que
#                recebe mensagens de atualização da topologia da rede
#
# CompContNet1 : Comportamento FIPA-ContractNet Iniciante que envia mensagens
#                CFP para outros agentes alimentadores solicitando propostas
#                de restauração. Este comportamento também faz a analise das
#                das propostas e analisa-as selecionando a que julga ser a
#                melhor
#
# CompContNet2 : Comportamento FIPA-ContractNet Participante que é acionado
#                quando um agente recebe uma mensagem do Tipo CFP enviando logo
#                em seguida uma proposta e caso esta seja selecinada realiza as
#                as análises de restrição para que seja possível a restauração

class CompRequest1(FipaRequestProtocol):
     '''CompRequest1

        Comportamento do tipo FIPA-Request Participante
        que o agente AA executa quando recebe mensagem
        do Agente AD com informações de TRIP no sistema
        Este comportamento também lança o comportamento
        ContractNet Iniciante, realiza a poda dos setores
        desenergizados e envia mensagem de atualização da
        topologia da rede para outros AA'''

    def __init__(self, agent):
        super(CompRequest1, self).__init__(
            agent=agent, message=None, is_initiator=False)

    def handle_request(self, message):

        # carrega o conteudo da mensagem recebida
        self.content = json.loads(message.content)

        if self.content['ref'] == 'R_04':
            display_message(self.agent.aid.name, 'Mensagem REQUEST recebida')

            # cria resposta para a mensagem recebida
            resposta = message.create_reply()
            resposta.set_performative(ACLMessage.INFORM)
            content = json.dumps({'ref': 'R_04'}, indent=4)
            resposta.set_content(content)
            self.agent.send(resposta)

            rams_desener = self.encontrar_rams_desener()

            message = ACLMessage(ACLMessage.CFP)
            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            message.set_content(json.dumps({'ref': 'CN_01',
                                            'dados': pickle.dumps(rams_desener)
                                            },
                                indent=4))

            for agente in self.agent.topologia['alimentadores'].keys():
                if self.agent.aid.localname not in agente:
                    message.add_receiver(AID(agente))

            # lança comportamento ContractNet na versão Iniciante
            comp = CompContNet1(self.agent, message)
            self.agent.behaviours.append(comp)
            comp.on_start()

    def encontrar_setor_sob_falta(self):
        chave_atuada = self.content['dados']['chaves'][0]
        chave = self.agent.alimentador.chaves[str(chave_atuada)]
        setor_1 = chave.n1
        setor_2 = chave.n2
        rnp = self.agent.alimentador.rnp_dic()
        prof_1 = rnp[setor_1.nome]
        prof_2 = rnp[setor_2.nome]
        if prof_1 > prof_2:
            return setor_1.nome
        else:
            return setor_2.nome

    def encontrar_rams_desener(self):
        setor_sob_falta = self.encontrar_setor_sob_falta()
        rnp = self.agent.alimentador.rnp_dic()
        prof = rnp[setor_sob_falta]
        setores_adjacentes = list()
        for i in range(np.size(self.agent.alimentador.rnp, axis=1)):
            if int(self.agent.alimentador.rnp[0, i]) == (int(prof) + 1):
                setores_adjacentes.append(self.agent.alimentador.rnp[1, i])

        chaves_de_isolacao = list()
        for chave in self.agent.alimentador.chaves.values():
            if (chave.n1.nome or chave.n2.nome) == setor_sob_falta:
                chaves_de_isolacao.append(chave.nome)

        rams_desener = list()
        setores_poda = list()
        for chave in chaves_de_isolacao:
            if self.agent.alimentador.chaves[chave].n1.nome != setor_sob_falta:
                # armazena setor raiz do ramo podado
                setor_poda = self.agent.alimentador.chaves[chave].n1.nome
                # poda o ramo do alimentador com defeito
                poda = self.agent.alimentador.podar(setor_poda, alterar_rnp=True)
            else:
                # armazena setor raiz do ramo podado
                setor_poda = self.agent.alimentador.chaves[chave].n2.nome
                # poda o ramo do alimentador com defeito
                poda = self.agent.alimentador.podar(setor_poda, alterar_rnp=True)

            # Atualiza a propria estrutura de dados
            self.agent.podas.append(poda)

            setores_poda.append(setor_poda)
            rams_desener.append(poda)

        # Envia mensagem para atualizar os outros agentes
        # que também têm uma representação da rede
        notificar_agentes(self.agent,
                          'poda',
                          self.agent.alimentador.nome,
                          setores_poda)

        return rams_desener


class CompRequest2(FipaRequestProtocol):
    '''CompRequest2 

       Comportamento do tipo FIPA-Request Participante que 
       recebe mensagens de atualização da topologia da rede'''

    def __init__(self, agent):
        super(CompRequest2, self).__init__(agent=agent,
                                           message=None,
                                           is_initiator=False)

    def handle_request(self, message):

        # carrega o conteudo da mensagem recebida
        self.content = json.loads(message.content)

        if self.content['ref'] == 'R_02':
            display_message(self.agent.aid.name, 'Mensagem REQUEST recebida')
            if self.content['dados']['tipo'] == 'poda':

                alimentador = self.agent.topologia['alimentadores'][
                    self.content['dados']['alimentador']
                ]

                self.setores = self.content['dados']['setores']
                for setor in self.setores:
                    poda = alimentador.podar(str(setor), alterar_rnp=True)
                    self.agent.podas.append(poda)

            elif self.content['dados']['tipo'] == 'insercao':
                alimentador = self.agent.topologia['alimentadores'][
                    self.content['dados']['alimentador']
                ]

                no, no_raiz = self.content['dados']['setores']

                for poda in self.agent.podas:

                    setores_poda = poda[0].keys()  # 0 : dict de setores da poda
                    if no_raiz in setores_poda:

                        alimentador.inserir_ramo(str(no), poda, str(no_raiz))
                        self.agent.podas.remove(poda)

            # cria resposta para a mensagem recebida
            resposta = message.create_reply()
            resposta.set_performative(ACLMessage.INFORM)
            content = json.dumps(
                {'ref': 'R_02',
                 'dados': 'Rede Atualizada'},
                indent=4)
            resposta.set_content(content)
            self.agent.send(resposta)

    def handle_inform(self, message):

        # carrega o conteudo da mensagem recebida
        self.content = json.loads(message.content)

        if self.content['ref'] == 'R_02':
            display_message(self.agent.aid.name, 'Mensagem INFORM recebida')

            self.agent.sincronizando = False


class CompContNet1(FipaContractNetProtocol):
    '''CompContNet1

       Comportamento FIPA-ContractNet Iniciante que envia mensagens
       CFP para outros agentes alimentadores solicitando propostas
       de restauração. Este comportamento também faz a analise das
       das propostas e analisa-as selecionando a que julga ser a 
       melhor'''

    def __init__(self, agent, message):
        super(CompContNet1, self).__init__(
            agent=agent, message=message, is_initiator=True)
        self.cfp = message

    def handle_all_proposes(self, proposes):
        """
        """

        super(CompContNet1, self).handle_all_proposes(proposes)

        melhor_propositor = None
        maior_potencia = 0.0
        demais_propositores = list()
        display_message(self.agent.aid.name, 'Analisando propostas...')

        i = 1
        for message in proposes:
            content = json.loads(message.content)
            potencia = content['dados']['potencia']
            display_message(self.agent.aid.name,
                            'Analisando proposta {i}'.format(i=i))
            display_message(self.agent.aid.name,
                            'Potencia Ofertada: {pot}'.format(pot=potencia))
            i += 1
            if potencia > maior_potencia:
                if melhor_propositor is not None:
                    demais_propositores.append(melhor_propositor)

                maior_potencia = potencia
                melhor_propositor = message.sender
            else:
                demais_propositores.append(message.sender)

        display_message(self.agent.aid.name,
                        'A melhor proposta foi de: {pot} VA'.format(
                            pot=maior_potencia))

        if demais_propositores != []:
            display_message(self.agent.aid.name,
                            'Enviando respostas de recusa...')
            resposta = ACLMessage(ACLMessage.REJECT_PROPOSAL)
            resposta.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            resposta.set_content(json.dumps({'ref': 'CN_03'}, indent=4))
            for agente in demais_propositores:
                resposta.add_receiver(agente)

            self.agent.send(resposta)

        if melhor_propositor is not None:
            display_message(self.agent.aid.name,
                            'Enviando resposta de aceitacao...')

            resposta = ACLMessage(ACLMessage.ACCEPT_PROPOSAL)
            resposta.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            resposta.set_content(
                json.dumps({'ref': 'CN_03',
                            'dados': json.loads(message.content)['dados']},
                           indent=4))
            resposta.add_receiver(melhor_propositor)
            self.agent.send(resposta)

    def handle_inform(self, message):
        """
        """
        super(CompContNet1, self).handle_inform(message)

        content = json.loads(message.content)

        if content['ref'] == 'CN_04':
            display_message(self.agent.aid.name, 'Mensagem INFORM recebida')

            if self.agent.podas is not []:
                display_message(self.agent.aid.name, 'Sera realizada nova tentativa de recomposicao')
                self.agent.agentes_solicitados.append(message.sender.localname)

                message = ACLMessage(ACLMessage.CFP)
                message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
                message.set_content(json.dumps({'ref': 'CN_01',
                                                'dados': pickle.dumps(self.agent.podas)
                                                },
                                    indent=4))

                agentes = list()
                for agent in self.agent.topologia['alimentadores'].keys():
                    if self.agent.aid.localname not in agent and agent not in self.agent.agentes_solicitados:
                        agentes.append(agent)
                        message.add_receiver(AID(agent))

                if not agentes == []:
                    # lança comportamento ContractNet na versão Iniciante
                    comp = CompContNet1(self.agent, message)
                    self.agent.behaviours.append(comp)
                    comp.on_start()
                    # self.agent.call_later(1.0, comp.on_start)
                else:
                    display_message(self.agent.aid.name, 'Nao ha mais possibilidades de solicitação de ajuda')

                self.agent.behaviours.remove(self)
                del self
            else:
                display_message(self.agent.aid.name, 'Comportameto de solicitação de ajuda encerrado')
                self.agent.agentes_solicitados = list()
                del self

    def handle_refuse(self, message):
        """
        """
        super(CompContNet1, self).handle_refuse(message)

        content = json.loads(message.content)

        if content['ref'] == 'CN_02':
            display_message(self.agent.aid.name, 'Mensagem REFUSE recebida')

    def handle_propose(self, message):
        """
        """
        super(CompContNet1, self).handle_propose(message)

        content = json.loads(message.content)

        if content['ref'] == 'CN_02':
            display_message(self.agent.aid.name, 'Mensagem PROPOSE recebida')


class CompContNet2(FipaContractNetProtocol):
    '''CompContNet2

       Comportamento FIPA-ContractNet Participante que é acionado
       quando um agente recebe uma mensagem do Tipo CFP enviando logo
       em seguida uma proposta e caso esta seja selecinada realiza as
       as análises de restrição para que seja possível a restauração'''
       
    def __init__(self, agent):
        super(CompContNet2, self).__init__(agent=agent,
                                           message=None,
                                           is_initiator=False)

    def handle_cfp(self, message):
        """
        """
        self.agent.call_later(1.0, self._handle_cfp, message)

    def _handle_cfp(self, message):
        """
        """
        super(CompContNet2, self).handle_cfp(message)
        self.message = message
        content = json.loads(message.content)

        if content['ref'] == 'CN_01':
            display_message(self.agent.aid.name, 'Mensagem CFP recebida')

            # self.agent.ramos_nao_energizados = pickle.loads(
            # json.loads(self.message.content)['dados'])

            chaves_recomp = selec_ramos_possiveis(self.agent.podas,
                                                  self.agent.alimentador)

            if chaves_recomp:
                # verifica a potencia disponivel nos
                # transformadores da subestacao
                potencia_disponivel = calcular_potencia_disponivel(self.agent.subestacao)

                resposta = self.message.create_reply()
                resposta.set_performative(ACLMessage.PROPOSE)
                resposta.set_content(
                    json.dumps({'ref': 'CN_02',
                                'dados': {'potencia': potencia_disponivel}}
                               ))
                self.agent.send(resposta)
            else:
                resposta = self.message.create_reply()
                resposta.set_performative(ACLMessage.REFUSE)
                resposta.set_content(json.dumps({'ref': 'CN_02'}))
                self.agent.send(resposta)

    def handle_reject_propose(self, message):
        """
        """
        super(CompContNet2, self).handle_reject_propose(message)
        
        content = json.loads(message.content)
        if content['ref'] == 'CN_03':
            display_message(self.agent.aid.name,
                            'Mensagem REJECT_PROPOSAL recebida')

    def handle_accept_propose(self, message):
        """
        """
        super(CompContNet2, self).handle_accept_propose(message)

        content = json.loads(message.content)
        if content['ref'] == 'CN_03':
            display_message(self.agent.aid.name,
                            'Mensagem ACCEPT_PROPOSE recebida')
            inserir_ramos_recursivo(self.agent,
                                    self.agent.alimentador,
                                    self.agent.subestacao,
                                    self.agent.podas)

            resposta = message.create_reply()
            resposta.set_performative(ACLMessage.INFORM)
            resposta.set_content(json.dumps({'ref': 'CN_04'}))
            self.agent.send(resposta)


class AgenteAlimentador(Agent):

    def __init__(self, aid):
        super(AgenteAlimentador, self).__init__(aid=aid, debug=False)

        self.topologia = carregar_topologia()

        self.alimentador = self.topologia['alimentadores'][
            self.aid.localname]

        for sub in self.topologia['subestacoes'].values():
            if self.aid.localname in sub.alimentadores.keys():
                self.subestacao = sub

        self.agentes_solicitados = list()
        self.podas = list()

        self.sincronizando = False

        comportamento_requisicao = CompRequest1(self)
        comportamento_requisicao_2 = CompRequest2(self)
        comportamento_contract_net = CompContNet2(self)

        self.behaviours.append(comportamento_requisicao)
        self.behaviours.append(comportamento_requisicao_2)
        self.behaviours.append(comportamento_contract_net)

    def carregar_info(self):
        pass


def notificar_agentes(agent, tipo, alimentador, setores):
    # Envia mensagem para atualizar os outros agentes
    # que também têm uma representação da rede
    if agent.sincronizando:
        agent.call_later(1.0,
                         notificar_agentes,
                         agent,
                         tipo,
                         alimentador,
                         setores)
    else:
        message = ACLMessage(ACLMessage.REQUEST)
        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_content(
            json.dumps({'ref': 'R_02',
                        'dados': {'tipo': tipo,
                                  'alimentador': alimentador,
                                  'setores': setores}
                        },
                       indent=4))

        agent.send_to_all(message)
        agent.sincronizando = True


def selec_ramos_possiveis(ramos, alimentador):

    chaves = alimentador.chaves.keys()
    chaves_recomp = list()
    for ramo in ramos:
        chaves_ramo = ramo[6]  # 6: posicao das chaves no ramo de poda
        for i in chaves_ramo.keys():
            if i in chaves:
                chaves_recomp.append(i)

    return chaves_recomp


def calcular_potencia_disponivel(subestacao):

    # calcula a potencia total consumida pelos alimentadores
    pot_cons = Fasor(real=0.0, imag=0.0, tipo=Fasor.Potencia)
    for alimentador in subestacao.alimentadores.values():
        pot_cons = pot_cons + alimentador.calcular_potencia()

    # calcula a potencia total dos transformadores da subestacao
    potencia_trafos = Fasor(real=0.0, imag=0.0, tipo=Fasor.Potencia)
    for trafo in subestacao.transformadores.values():
        potencia_trafos = potencia_trafos + trafo.potencia

    return potencia_trafos.mod - pot_cons.mod


def verificar_carregamento_dos_condutores(agent, subestacao):
    """verifica o carregamento dos condutores após inserção
    de ramo afetado
    """
    for alimentador in subestacao.alimentadores.values():
        for trecho in alimentador.trechos.values():
            if trecho.fluxo.mod > trecho.condutor.ampacidade:
                display_message(agent.aid.name, 'Restrição de carregamento de condutores ' \
                      'atingida no trecho {t}'.format(t=trecho.nome))
                return trecho.nome
    else:
        return None


def verificar_nivel_de_tensao(agent, subestacao):
    """verifica nivel de tensao nos nós de carga
    """
    for alimentador in subestacao.alimentadores.values():
            for no in alimentador.nos_de_carga.values():
                if no.tensao.mod < 0.95 * subestacao.tensao.mod or \
                   no.tensao.mod > 1.05 * subestacao.tensao.mod:
                    display_message(agent.aid.name, 'Restrição de Tensão atingida ' \
                          'no nó de carga {no}'.format(no=no.nome))
                    return no.nome
    else:
        return None


def identificar_setor_de_insercao(ramo, alimentador):
    """retorna uma lista com pares do tipo
    setor a ser recomposto, setor do
    ramo de recomposição
    """
    # carrega as chaves do alimentador de recomposição
    chaves_alimen = alimentador.chaves

    # carrega as chaves do ramo a ser recomposto
    chaves_ramo = ramo[6]  # 6: posicao das chaves no ramo de poda

    # verifica quais chaves existem em comum entre estes ramos
    chaves_recomp = [i for i in chaves_alimen.keys()
                     if i in chaves_ramo.keys()]

    pares_setores_recomp = []
    # se não existirem chaves em comum
    # este método retorna uma lista vazia
    if chaves_recomp == []:
        return []
    else:
        # pecorre as chaves em comum
        for i in chaves_recomp:
            # carrega o objeto chave
            chave = chaves_alimen[i]
            # ordena os setores ligados a chave de recomposição
            # em um par do tipo setor do alimentador de recomposição
            # setor do alimentador a ser recomposto
            if chave.n1.nome in alimentador.setores.keys():
                pares_setores_recomp.append((chave.n1.nome, chave.n2.nome))
            elif chave.n2.nome in alimentador.setores.keys():
                pares_setores_recomp.append((chave.n2.nome, chave.n1.nome))
        return pares_setores_recomp


def podar_setor_mais_profundo(agent,
                              alimentador,
                              setores_analisados,
                              setores_mais_profundos,
                              rnp_de_setor,
                              profundidade):
    """metodo utilizado sempre que qualquer uma das restrições: potencia,
    carregamento dos condutores, ou níveis de tensão; sejam atingidas.
    Recebe como parâmetro uma lista com os setores que têm a profundidade
    indicada pelo parâmetro profundidade e que ainda não foram podados.
    O metodo calcula se ainda existem setores a serem podados e caso
    existam realiza a poda, retornando os setores que ainda podem ser podados
    para a profundidade dada.
    """

    # ordena a lista de setores analisados
    setores_analisados.sort()

    # -se- a lista setores_mais_profundos estiver vazia e a lista
    # setores_analisados contiver todos os setores do alimentador
    # então não existem mais possibilidades
    # -se não- a lista de setores_mais_profundos é atualizada com
    # a profundidade reduzida de menos 1
    if setores_mais_profundos == [] and \
       setores_analisados != list(rnp_de_setor[1, :]).sort():

        # encontra quais os setores com maior profundidade
        # no ramo podado
        setores_mais_profundos = list(
            rnp_de_setor[1, np.where(
                rnp_de_setor[0, :] == str(profundidade))])
        profundidade -= 1
    else:
        display_message(agent.aid.name, 'A recomposicao do ramo nao foi possivel!')
        return None

    # retira o setor a ser podado da lista de setores mais profundos
    setor = setores_mais_profundos.pop(0)[0]
    # insere o setor podado na lista de setores analisados
    setores_analisados.append(setor)

    display_message(agent.aid.name, 'Poda do setor: {setor}'.format(setor=setor))
    # realiza a poda do setor
    poda = alimentador.podar(setor, alterar_rnp=True)

    # Envia mensagem para atualizar os outros agentes
    # que também têm uma representação da rede
    notificar_agentes(agent,
                      'poda',
                      alimentador.nome,
                      setor)
    # notificar_agentes(agent,
    #                  'poda',
    #                  alimentador.nome,
    #                  setor)

    # retorna uma tupla de setores_mais_profundos
    return setores_analisados, setores_mais_profundos, profundidade, poda


def inserir_ramos_recursivo(agent, alimentador, subestacao, ramos):
    ramos_2 = list()

    # for percorre os ramos afetados tentando a recomposicao de cada um deles!
    for ramo in ramos:
        # identifica quais setores fazem vizinhança ao alimentador
        # afetado e quais setores deste alimentador fazem vizinhança
        # para que possa ser realizada a inserção
        pares_setores_recomp = identificar_setor_de_insercao(ramo, alimentador)

        if pares_setores_recomp == []:
            ramos_2.append(ramo)
        else:
            no, no_raiz = pares_setores_recomp[0]

            # inserção de todo o ramo na arvore do alimentador
            alimentador.inserir_ramo(no, ramo, no_raiz)

            display_message(agent.aid.name, 'Inserção de ramo no alimentador')
            print alimentador.rnp

            # Envia mensagem para atualizar os outros agentes
            # que também têm uma representação da rede
            notificar_agentes(agent,
                              'insercao',
                              alimentador.nome,
                              (no, no_raiz))

            # verificação da potencia fornecida pelos transformadores
            potencia_disponivel = calcular_potencia_disponivel(subestacao)

            display_message(agent.aid.name, 'Potencia disponivel após inserção de ramo: {pot} MVA'.format(
                pot=potencia_disponivel / 1e6))

            setores_mais_profundos = []
            setores_analisados = []
            poda_de_setores = []

            rnp_de_setor = ramo[2]  # 2 : RNP de setor da poda
            prof = int(max(rnp_de_setor[0, :]))

            setores_ramo = list(rnp_de_setor[1, :])
            setores_ramo.sort()

            while potencia_disponivel < 0.0:
                # caso haja violação nas potências dos trafos, o sistema
                # irá podar os setores de maior profundidade do ramo
                # inserido até que a violação deixe de existir

                info_poda = podar_setor_mais_profundo(agent,
                                                      alimentador,
                                                      setores_analisados,
                                                      setores_mais_profundos,
                                                      rnp_de_setor,
                                                      prof)
                if info_poda is None:
                    break
                else:
                    (setores_analisados,
                     setores_mais_profundos,
                     prof,
                     poda) = info_poda
                    poda_de_setores.append(poda)

                # atualização da potencia fornecida pelos transformadores
                potencia_disponivel = calcular_potencia_disponivel(subestacao)
                display_message(agent.aid.name, 'Potencia disponivel após realizaçao de poda: {pot} MVA'.format(
                    pot=potencia_disponivel / 1e6))
            else:
                # se não houver violação na potencia
                # dos trafos a restrição de carregamento
                # dos condutores  e nível de tensão são verificadas

                subestacao.calcular_fluxo_de_carga()
                trecho = verificar_carregamento_dos_condutores(agent, subestacao)

                while trecho is not None:
                    info_poda = podar_setor_mais_profundo(agent,
                                                          alimentador,
                                                          setores_analisados,
                                                          setores_mais_profundos,
                                                          rnp_de_setor,
                                                          prof)
                    (setores_analisados,
                     setores_mais_profundos,
                     prof,
                     poda) = info_poda

                    poda_de_setores.append(poda)

                    if info_poda is None:
                        break
                    else:
                        (setores_analisados,
                         setores_mais_profundos,
                         prof,
                         poda) = info_poda

                    # calculo de fluxo de carga no alimentador
                    subestacao.calcular_fluxo_de_carga()
                    trecho = verificar_carregamento_dos_condutores(agent, subestacao)
                    if trecho is not None:
                        display_message(agent.aid.name, 'Trecho {tr} em sobrecarga'.format(tr=trecho))
                else:
                    no = verificar_nivel_de_tensao(agent, subestacao)

                    while no is not None:
                        info_poda = podar_setor_mais_profundo(agent,
                                                              alimentador,
                                                              setores_analisados,
                                                              setores_mais_profundos,
                                                              rnp_de_setor,
                                                              prof)
                        (setores_analisados,
                         setores_mais_profundos,
                         prof,
                         poda) = info_poda

                        poda_de_setores.append(poda)
                        if info_poda is None:
                            break
                        else:
                            (setores_analisados,
                             setores_mais_profundos,
                             prof,
                             poda) = info_poda
                            poda_de_setores.append(poda)
                        # calculo de fluxo de carga no alimentador
                        subestacao.calcular_fluxo_de_carga()
                        no = verificar_nivel_de_tensao(agent, subestacao)
                        if no is not None:
                            display_message(agent.aid.name, 'No de carga {no} com' \
                                                            'violacao de tensao'.format(no=no))

                if trecho is None and no is None:
                    display_message(agent.aid.name, 'Recomposição do ramo realizada')
                    print alimentador.rnp
                    inserir_ramos_recursivo(agent, alimentador, subestacao, ramos_2)
                elif trecho is not None:
                    return
                elif no is not None:
                    return
    return


if __name__ == "__main__":
    aa_1 = AgenteAlimentador(AID(name='S1_AL1'))
    aa_2 = AgenteAlimentador(AID(name='S1_AL2'))
    aa_3 = AgenteAlimentador(AID(name='S2_AL1'))

    agents_list = list([aa_1, aa_2, aa_3])

    start_loop(agents_list)
