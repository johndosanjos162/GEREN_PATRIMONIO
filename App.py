import streamlit as st
import streamlit.components.v1 as components
import json
import random
import time
from datetime import datetime

st.set_page_config(
    page_title="PMSC 3D – Estudo Imersivo",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==================================================================
# DISTRIBUIÇÃO OFICIAL (Edital PMSC / Instituto AOCP)
# ==================================================================
DISTRIBUICAO = {
    "Legislação Institucional": 10,
    "Direito Constitucional": 8,
    "Língua Portuguesa": 8,
    "Direito Penal Comum": 6,
    "Direito Processual Penal Comum": 6,
    "Direito Penal Militar": 6,
    "Legislação Especial": 6,
    "Legislação de Trânsito": 5,
    "Informática": 5,
}
TOTAL = sum(DISTRIBUICAO.values())  # 60

# ==================================================================
# BANCO DE QUESTÕES — estilo AOCP / PMSC (150+)
# ==================================================================
BANCO_QUESTOES = {
    "Legislação Institucional": [
        {"pergunta": "Segundo o art. 42 da CF/88, os membros das Polícias Militares e Corpos de Bombeiros Militares são considerados:",
         "alternativas": ["A) Servidores públicos civis da União.", "B) Militares dos Estados, do Distrito Federal e dos Territórios.", "C) Agentes políticos de segurança nacional.", "D) Servidores federais com regime jurídico especial.", "E) Empregados públicos vinculados ao Ministério da Justiça."],
         "correta": "B"},
        {"pergunta": "A Lei nº 13.967/2019 alterou o Decreto-Lei nº 667/69 para dispor sobre a exclusão de militares estaduais. Assinale a alternativa que NÃO corresponde a uma inovação dessa lei:",
         "alternativas": ["A) Instituição de conselhos de disciplina.", "B) Ampliação do contraditório e da ampla defesa.", "C) Eliminação da possibilidade de recurso administrativo.", "D) Maior segurança jurídica nos processos disciplinares.", "E) Estabelecimento de prazos para conclusão dos processos."],
         "correta": "C"},
        {"pergunta": "São pilares da organização da Polícia Militar, conforme o Estatuto da PMSC:",
         "alternativas": ["A) Hierarquia e disciplina.", "B) Autonomia e descentralização.", "C) Sindicalização e representação.", "D) Eleição de comandantes.", "E) Rotatividade obrigatória de funções."],
         "correta": "A"},
        {"pergunta": "Sobre o Decreto-Lei nº 667/1969, que reorganizou as Polícias Militares, é correto afirmar:",
         "alternativas": ["A) Subordinou as PMs ao Ministério da Defesa em tempo de paz.", "B) Estabeleceu que as PMs são forças auxiliares e reserva do Exército.", "C) Criou a Guarda Nacional em substituição às PMs.", "D) Extinguiu as Polícias Militares estaduais.", "E) Transferiu às PMs a competência da Justiça Militar da União."],
         "correta": "B"},
        {"pergunta": "Conforme o art. 144, §5º, da CF/88, às Polícias Militares cabem:",
         "alternativas": ["A) Apenas o policiamento de trânsito.", "B) A polícia judiciária e a apuração de infrações penais.", "C) A polícia ostensiva e a preservação da ordem pública.", "D) Exclusivamente a segurança de autoridades.", "E) A defesa civil e o combate a incêndios."],
         "correta": "C"},
        {"pergunta": "A Lei nº 14.751/2023 (Lei Orgânica Nacional das Polícias Militares) estabelece que as PMs são instituições:",
         "alternativas": ["A) Civis, organizadas sem hierarquia.", "B) Militares, organizadas com base na hierarquia e disciplina.", "C) Subordinadas ao Ministério Público.", "D) Vinculadas ao Poder Judiciário.", "E) De natureza privada, com fins lucrativos."],
         "correta": "B"},
        {"pergunta": "Sobre as vedações constitucionais aos militares (art. 142, §3º, CF), assinale a alternativa CORRETA:",
         "alternativas": ["A) Podem sindicalizar-se e fazer greve.", "B) Podem filiar-se a partidos políticos.", "C) Não podem sindicalizar-se, fazer greve nem filiar-se a partidos enquanto em serviço ativo.", "D) Podem fazer greve apenas em tempo de paz.", "E) Podem filiar-se a partidos, mas não podem fazer greve."],
         "correta": "C"},
        {"pergunta": "A hierarquia militar, conforme a doutrina, subdivide-se em:",
         "alternativas": ["A) Circular e funcional.", "B) Simples e composta.", "C) Vertical e horizontal.", "D) Interna e externa.", "E) Formal e informal."],
         "correta": "A"},
        {"pergunta": "Sobre postos e graduações, é correto afirmar:",
         "alternativas": ["A) Postos são dos praças e graduações dos oficiais.", "B) Postos são dos oficiais e graduações dos praças.", "C) Postos e graduações são sinônimos.", "D) Apenas oficiais possuem posto e graduação.", "E) Apenas praças possuem posto e graduação."],
         "correta": "B"},
        {"pergunta": "A passagem do militar à inatividade pode ocorrer por:",
         "alternativas": ["A) Reserva remunerada ou reforma.", "B) Licença ou afastamento.", "C) Suspensão ou cassação.", "D) Transferência ou remoção.", "E) Promoção ou ascensão."],
         "correta": "A"},
        {"pergunta": "Sobre o Conselho de Disciplina na PMSC, é correto afirmar:",
         "alternativas": ["A) É órgão de natureza judicial.", "B) É órgão de natureza administrativa, destinado a julgar transgressões disciplinares.", "C) É órgão subordinado ao Ministério Público.", "D) É órgão de competência exclusiva do Poder Judiciário.", "E) É órgão consultivo sem poder decisório."],
         "correta": "B"},
        {"pergunta": "Sobre a diferença entre crime militar e transgressão disciplinar, é correto afirmar:",
         "alternativas": ["A) São sinônimos.", "B) Crime militar é julgado pela Justiça Militar; transgressão, por autoridade administrativa militar.", "C) Ambos são julgados pela Justiça Comum.", "D) Transgressão é sempre mais grave que crime militar.", "E) Crime militar não admite pena privativa de liberdade."],
         "correta": "B"},
        {"pergunta": "Sobre a sindicância na PMSC, é correto afirmar:",
         "alternativas": ["A) Tem natureza penal.", "B) É procedimento administrativo sumário para apurar faltas leves.", "C) Substitui o inquérito policial.", "D) Só pode ser instaurada pelo Governador.", "E) É vedada pela legislação estadual."],
         "correta": "B"},
        {"pergunta": "Compete ao Comandante-Geral da PMSC, entre outras atribuições:",
         "alternativas": ["A) Julgar crimes militares.", "B) Comandar a corporação, decidindo sobre questões administrativas e operacionais.", "C) Legislar sobre matérias de segurança pública.", "D) Aplicar penas de natureza criminal.", "E) Substituir o Governador do Estado."],
         "correta": "B"},
        {"pergunta": "A Lei nº 13.967/2019 vedou a pena de prisão disciplinar, estabelecendo que as punições disciplinares militares devem respeitar:",
         "alternativas": ["A) Apenas a hierarquia.", "B) Apenas a disciplina.", "C) Os princípios do contraditório e da ampla defesa.", "D) Somente decisões do comandante.", "E) O sigilo absoluto."],
         "correta": "C"},
        {"pergunta": "Sobre a competência da PMSC, conforme o art. 144 da CF/88 e o Estatuto estadual, é correto afirmar:",
         "alternativas": ["A) Exerce apenas polícia judiciária.", "B) Exerce a polícia ostensiva e a preservação da ordem pública no âmbito do Estado.", "C) Exerce atividades exclusivas da União.", "D) Não pode atuar no policiamento de trânsito.", "E) Atua apenas em áreas rurais."],
         "correta": "B"},
        {"pergunta": "Sobre o Código de Ética dos militares estaduais, é correto afirmar:",
         "alternativas": ["A) Não há previsão legal.", "B) Aplica-se apenas aos oficiais.", "C) Aplica-se a todos os militares, orientando a conduta funcional.", "D) Aplica-se apenas em tempo de guerra.", "E) Substitui o Código Penal Militar."],
         "correta": "C"},
        {"pergunta": "A Lei Orgânica Nacional das Polícias Militares (Lei nº 14.751/2023) define como princípios institucionais, entre outros:",
         "alternativas": ["A) Hierarquia, disciplina, legalidade, impessoalidade e eficiência.", "B) Lucro, competição e livre iniciativa.", "C) Autonomia absoluta e sindicalização.", "D) Subordinação ao Poder Judiciário.", "E) Sigilo absoluto e discricionariedade irrestrita."],
         "correta": "A"},
    ],
    "Direito Constitucional": [
        {"pergunta": "Conforme o art. 144 da CF/88, a segurança pública é dever do Estado, direito e responsabilidade de todos. São órgãos de segurança pública, EXCETO:",
         "alternativas": ["A) Polícia Federal.", "B) Polícia Rodoviária Federal.", "C) Polícias Militares e Corpos de Bombeiros Militares.", "D) Guardas Municipais.", "E) Forças Armadas."],
         "correta": "E"},
        {"pergunta": "Assinale a alternativa que NÃO corresponde a um direito fundamental previsto no art. 5º da CF/88:",
         "alternativas": ["A) Direito de petição aos Poderes Públicos.", "B) Direito de reunião pacífica, sem armas, em locais abertos.", "C) Direito à livre manifestação do pensamento, vedado o anonimato.", "D) Direito de greve dos militares.", "E) Direito à inviolabilidade do domicílio."],
         "correta": "D"},
        {"pergunta": "São princípios expressos da Administração Pública no caput do art. 37 da CF/88:",
         "alternativas": ["A) Legalidade, impessoalidade, moralidade, publicidade e eficiência.", "B) Legalidade, economicidade, razoabilidade e proporcionalidade.", "C) Hierarquia, disciplina, legalidade e impessoalidade.", "D) Moralidade, celeridade, economicidade e eficiência.", "E) Publicidade, motivação, ampla defesa e contraditório."],
         "correta": "A"},
        {"pergunta": "Quanto à responsabilidade civil do Estado (art. 37, §6º, CF), é correto afirmar:",
         "alternativas": ["A) É subjetiva, exigindo comprovação de dolo ou culpa do agente.", "B) É objetiva, dispensando a comprovação de dolo ou culpa do agente.", "C) Aplica-se apenas a atos comissivos.", "D) Não admite direito de regresso contra o agente.", "E) Depende de prévia autorização legislativa."],
         "correta": "B"},
        {"pergunta": "O remédio constitucional adequado para proteger a liberdade de locomoção é:",
         "alternativas": ["A) Habeas data.", "B) Mandado de segurança.", "C) Habeas corpus.", "D) Mandado de injunção.", "E) Ação popular."],
         "correta": "C"},
        {"pergunta": "O remédio constitucional destinado a assegurar o conhecimento de informações relativas à pessoa do impetrante é:",
         "alternativas": ["A) Habeas corpus.", "B) Habeas data.", "C) Mandado de segurança.", "D) Ação popular.", "E) Mandado de injunção."],
         "correta": "B"},
        {"pergunta": "Sobre o mandado de segurança, é correto afirmar:",
         "alternativas": ["A) Protege direito líquido e certo não amparado por habeas corpus ou habeas data.", "B) Substitui o habeas corpus.", "C) Só pode ser impetrado por pessoa jurídica.", "D) Só é cabível contra ato judicial.", "E) Tem prazo de 30 dias para impetração."],
         "correta": "A"},
        {"pergunta": "A ação popular pode ser proposta por:",
         "alternativas": ["A) Apenas pelo Ministério Público.", "B) Apenas por pessoa jurídica.", "C) Qualquer cidadão no gozo dos direitos políticos.", "D) Apenas por servidores públicos.", "E) Apenas por partidos políticos."],
         "correta": "C"},
        {"pergunta": "Sobre os direitos sociais previstos na CF/88, é correto afirmar que incluem:",
         "alternativas": ["A) Apenas saúde e educação.", "B) Saúde, educação, moradia, trabalho, lazer, segurança, previdência, entre outros.", "C) Apenas direitos trabalhistas.", "D) Apenas direitos previdenciários.", "E) Apenas direitos culturais."],
         "correta": "B"},
        {"pergunta": "Sobre a nacionalidade brasileira, é correto afirmar que são brasileiros natos:",
         "alternativas": ["A) Apenas os nascidos no Brasil.", "B) Os nascidos no Brasil, mesmo de pais estrangeiros, desde que não estejam a serviço de seu país.", "C) Apenas os filhos de brasileiros nascidos no exterior.", "D) Apenas os naturalizados.", "E) Todos os residentes no Brasil."],
         "correta": "B"},
        {"pergunta": "São privativos de brasileiros natos, entre outros cargos:",
         "alternativas": ["A) Presidente da República, Governador e Prefeito.", "B) Presidente da República, Presidente do Senado, Presidente da Câmara e Ministro do STF.", "C) Apenas Presidente da República.", "D) Apenas Ministro do STF.", "E) Apenas cargos militares."],
         "correta": "B"},
        {"pergunta": "Sobre os direitos políticos, o alistamento eleitoral é:",
         "alternativas": ["A) Facultativo para todos.", "B) Obrigatório para maiores de 18 anos, salvo exceções constitucionais.", "C) Vedado aos analfabetos.", "D) Vedado aos maiores de 70 anos.", "E) Restrito aos militares."],
         "correta": "B"},
        {"pergunta": "O princípio da legalidade na Administração Pública significa que:",
         "alternativas": ["A) O administrador pode fazer tudo o que a lei não proíbe.", "B) O administrador só pode agir conforme a lei autorize.", "C) A lei não vincula a Administração.", "D) A Administração pode editar leis.", "E) O particular só pode agir se a lei autorizar."],
         "correta": "B"},
        {"pergunta": "O princípio da impessoalidade impõe que a Administração:",
         "alternativas": ["A) Trate os administrados conforme critérios pessoais.", "B) Atue sem favorecimentos ou perseguições, visando o interesse público.", "C) Promova seus agentes.", "D) Divulgue apenas atos de interesse do governante.", "E) Contrate apenas parentes."],
         "correta": "B"},
        {"pergunta": "Sobre a organização do Estado brasileiro, é correto afirmar:",
         "alternativas": ["A) O Brasil é um Estado unitário.", "B) O Brasil é uma federação composta por União, Estados, Distrito Federal e Municípios.", "C) O Brasil é uma confederação.", "D) O Brasil é um império.", "E) O Brasil é um Estado teocrático."],
         "correta": "B"},
        {"pergunta": "Compete privativamente à União, entre outras matérias:",
         "alternativas": ["A) Legislar sobre direito civil, penal e processual.", "B) Legislar sobre direito estadual.", "C) Legislar apenas sobre matéria tributária estadual.", "D) Legislar apenas sobre trânsito municipal.", "E) Legislar apenas sobre segurança estadual."],
         "correta": "A"},
        {"pergunta": "Sobre o Poder Executivo, é correto afirmar:",
         "alternativas": ["A) O Presidente da República é eleito por voto indireto.", "B) O Presidente da República é eleito por voto direto, secreto e universal, para mandato de 4 anos.", "C) O mandato presidencial é de 6 anos.", "D) O Presidente não pode ser reeleito.", "E) O Presidente é escolhido pelo Congresso."],
         "correta": "B"},
        {"pergunta": "Sobre o controle de constitucionalidade, é correto afirmar que a ADI (Ação Direta de Inconstitucionalidade) pode ser proposta por:",
         "alternativas": ["A) Qualquer cidadão.", "B) Apenas pelo Presidente da República.", "C) Diversos legitimados, entre eles o Presidente, as Mesas do Senado e da Câmara, o Procurador-Geral da República e entidades de classe.", "D) Apenas por partidos políticos.", "E) Apenas por Governadores."],
         "correta": "C"},
    ],
    "Língua Portuguesa": [
        {"pergunta": "Assinale a alternativa em que o uso da crase está CORRETO:",
         "alternativas": ["A) Vou à Brasília amanhã.", "B) Refiro-me à pessoas honestas.", "C) Entreguei o relatório à Vossa Senhoria.", "D) Ele começou à trabalhar cedo.", "E) Cheguei à casa de meus pais."],
         "correta": "E"},
        {"pergunta": "Em 'Fazem três anos que não o vejo', o verbo 'fazer' está:",
         "alternativas": ["A) Corretamente flexionado, pois indica ação do sujeito.", "B) Incorreto, pois deveria ser impessoal: 'Faz três anos'.", "C) Correto, pois se trata de sujeito composto.", "D) Correto, pois há sujeito oculto.", "E) Incorreto por erro de regência."],
         "correta": "B"},
        {"pergunta": "Em qual alternativa há ERRO de concordância verbal?",
         "alternativas": ["A) Existem muitos problemas a resolver.", "B) Fazem dois anos que ele saiu.", "C) Chegou o pai e a mãe do aluno.", "D) Havia poucos alunos na sala.", "E) Devem haver soluções viáveis."],
         "correta": "B"},
        {"pergunta": "Assinale a alternativa que apresenta ERRO de regência:",
         "alternativas": ["A) Assisti ao filme ontem.", "B) Aspiro ao cargo de soldado.", "C) Obedeci ao regulamento.", "D) Prefiro estudar mais do que trabalhar.", "E) Informei o fato ao comandante."],
         "correta": "D"},
        {"pergunta": "Assinale a alternativa em que a pontuação está CORRETA:",
         "alternativas": ["A) O soldado, chegou cedo ao quartel.", "B) O soldado chegou, cedo ao quartel.", "C) O soldado chegou cedo, ao quartel.", "D) O soldado, que é dedicado, chegou cedo.", "E) O soldado chegou cedo; ao quartel."],
         "correta": "D"},
        {"pergunta": "Assinale a alternativa em que todas as palavras estão grafadas CORRETAMENTE:",
         "alternativas": ["A) Ecesso, comprehendo, desenvolvimento.", "B) Exceção, compreendo, desenvolvimento.", "C) Esceção, compreendo, desenvovimento.", "D) Excessão, compreendo, desenvolvimento.", "E) Exeção, compreendo, desenvimento."],
         "correta": "B"},
        {"pergunta": "A frase 'O gerente, que é experiente, comandou a operação' apresenta qual tipo de oração subordinada adjetiva?",
         "alternativas": ["A) Restritiva.", "B) Explicativa.", "C) Apositiva.", "D) Consecutiva.", "E) Condicional."],
         "correta": "B"},
        {"pergunta": "Em 'Embora estivesse cansado, o soldado cumpriu a missão', a oração sublinhada é subordinada adverbial:",
         "alternativas": ["A) Causal.", "B) Concessiva.", "C) Condicional.", "D) Consecutiva.", "E) Final."],
         "correta": "B"},
        {"pergunta": "Assinale a alternativa em que o verbo está na voz passiva analítica:",
         "alternativas": ["A) O soldado prendeu o suspeito.", "B) O suspeito foi preso pelo soldado.", "C) Prendeu-se o suspeito.", "D) O soldado se machucou.", "E) O soldado machucou o suspeito."],
         "correta": "B"},
        {"pergunta": "A palavra 'cômputo' é acentuada por ser:",
         "alternativas": ["A) Oxítona terminada em 'o'.", "B) Paroxítona terminada em 'o'.", "C) Proparoxítona.", "D) Monossílaba tônica.", "E) Hiato."],
         "correta": "C"},
        {"pergunta": "Assinale a alternativa em que o uso de 'mim' está CORRETO:",
         "alternativas": ["A) Para mim fazer o relatório, preciso de tempo.", "B) Entre mim e você, há confiança.", "C) Chegou uma carta para mim responder.", "D) Deixei ele mim ajudar.", "E) Isso é para mim fazer."],
         "correta": "B"},
        {"pergunta": "Em 'Ele disse que viria amanhã', a partícula 'que' introduz:",
         "alternativas": ["A) Oração subordinada substantiva objetiva direta.", "B) Oração subordinada adjetiva.", "C) Oração coordenada sindética.", "D) Oração subordinada adverbial.", "E) Oração principal."],
         "correta": "A"},
        {"pergunta": "Assinale a alternativa em que há ERRO de concordância nominal:",
         "alternativas": ["A) É proibido entrada de estranhos.", "B) É proibida a entrada de estranhos.", "C) Ela mesma fez o relatório.", "D) Segue anexo as fotos.", "E) Os documentos seguem anexos."],
         "correta": "D"},
        {"pergunta": "Assinale a alternativa em que a palavra 'porque' está usada CORRETAMENTE:",
         "alternativas": ["A) Porque você não veio?", "B) Não sei por que ele saiu.", "C) Por quê ele saiu?", "D) O porquê de sua ausência é por que está doente.", "E) Porque? Não entendo."],
         "correta": "B"},
        {"pergunta": "Em 'Havia muitos candidatos na sala', o verbo 'haver' é:",
         "alternativas": ["A) Pessoal e concorda com o sujeito.", "B) Impessoal, permanecendo na 3ª pessoa do singular.", "C) De ligação.", "D) Transitivo indireto.", "E) Pronominal."],
         "correta": "B"},
        {"pergunta": "Assinale a alternativa que apresenta um exemplo de metáfora:",
         "alternativas": ["A) Seus olhos são duas estrelas.", "B) Ele correu como um foguete.", "C) O vento sussurrava segredos.", "D) Morrer de rir.", "E) Chorei rios de lágrimas."],
         "correta": "A"},
        {"pergunta": "Assinale a alternativa em que o sujeito é indeterminado:",
         "alternativas": ["A) O soldado chegou.", "B) Roubaram minha carteira.", "C) Eu cheguei cedo.", "D) Todos chegaram.", "E) O cão latiu."],
         "correta": "B"},
        {"pergunta": "Em 'Ele comprou um carro novo', o termo 'um carro novo' é:",
         "alternativas": ["A) Sujeito.", "B) Objeto direto.", "C) Objeto indireto.", "D) Predicativo do sujeito.", "E) Adjunto adnominal."],
         "correta": "B"},
        {"pergunta": "Em 'O aluno inteligente passou no concurso', o termo 'inteligente' é:",
         "alternativas": ["A) Predicativo do sujeito.", "B) Adjunto adnominal.", "C) Complemento nominal.", "D) Aposto.", "E) Vocativo."],
         "correta": "B"},
        {"pergunta": "Assinale a alternativa em que o uso de 'mais' está CORRETO:",
         "alternativas": ["A) Ele chegou mais tarde que o irmão.", "B) Ele estuda mais, mas não aprende.", "C) Eu quero mais um copo de água.", "D) O mais importante é estudar.", "E) Ele é o mais alto da turma."],
         "correta": "E"},
    ],
    "Direito Penal Comum": [
        {"pergunta": "Sobre a legítima defesa (art. 25 do CP), é correto afirmar:",
         "alternativas": ["A) Exige agressão injusta, atual ou iminente, e uso moderado dos meios necessários.", "B) Só é admitida contra agressão armada.", "C) Só pode ser invocada por policiais.", "D) Admite excesso doloso sem qualquer consequência.", "E) Exige sempre agressão consumada."],
         "correta": "A"},
        {"pergunta": "A principal diferença entre furto (art. 155) e roubo (art. 157) do CP é:",
         "alternativas": ["A) O valor do bem subtraído.", "B) O local do crime.", "C) O uso de violência ou grave ameaça no roubo.", "D) O horário da prática.", "E) A condição da vítima."],
         "correta": "C"},
        {"pergunta": "O homicídio qualificado (art. 121, §2º, CP) NÃO inclui, entre suas qualificadoras:",
         "alternativas": ["A) Motivo torpe.", "B) Meio cruel.", "C) Emboscada.", "D) Motivo de relevante valor social.", "E) Feminicídio."],
         "correta": "D"},
        {"pergunta": "São crimes contra a honra previstos no CP, EXCETO:",
         "alternativas": ["A) Calúnia.", "B) Difamação.", "C) Injúria.", "D) Constrangimento ilegal.", "E) Todas as anteriores são crimes contra a honra."],
         "correta": "D"},
        {"pergunta": "O estado de necessidade (art. 24 do CP) é causa de:",
         "alternativas": ["A) Aumento de pena.", "B) Exclusão da ilicitude.", "C) Exclusão da culpabilidade.", "D) Extinção da punibilidade.", "E) Suspensão condicional do processo."],
         "correta": "B"},
        {"pergunta": "São causas de exclusão da ilicitude, EXCETO:",
         "alternativas": ["A) Legítima defesa.", "B) Estado de necessidade.", "C) Estrito cumprimento do dever legal.", "D) Exercício regular de direito.", "E) Inimputabilidade penal."],
         "correta": "E"},
        {"pergunta": "A imputabilidade penal no Brasil, em regra, começa aos:",
         "alternativas": ["A) 16 anos.", "B) 18 anos.", "C) 21 anos.", "D) 14 anos.", "E) 20 anos."],
         "correta": "B"},
        {"pergunta": "A tentativa (art. 14, II, CP) ocorre quando o agente:",
         "alternativas": ["A) Pratica todos os atos e consuma o crime.", "B) Inicia a execução, mas não a consuma por circunstâncias alheias à sua vontade.", "C) Desiste voluntariamente.", "D) Pratica atos preparatórios.", "E) Age em legítima defesa."],
         "correta": "B"},
        {"pergunta": "A desistência voluntária e o arrependimento eficaz são hipóteses de:",
         "alternativas": ["A) Tentativa.", "B) Consumação.", "C) Crime impossível.", "D) Não punibilidade da tentativa (art. 15 CP).", "E) Agravação da pena."],
         "correta": "D"},
        {"pergunta": "Sobre o concurso de pessoas, é correto afirmar:",
         "alternativas": ["A) Todos respondem pelo mesmo crime, sempre.", "B) Cada um responde na medida de sua culpabilidade.", "C) Só há concurso com duas ou mais pessoas.", "D) Não existe no CP brasileiro.", "E) Só se aplica a crimes militares."],
         "correta": "B"},
        {"pergunta": "O crime continuado (art. 71 do CP) ocorre quando o agente:",
         "alternativas": ["A) Pratica um único crime.", "B) Pratica dois ou mais crimes da mesma espécie, com condições semelhantes, tempo, lugar e modo de execução.", "C) Pratica crimes de espécies diferentes.", "D) Age em legítima defesa.", "E) Pratica crimes com intervalo superior a 1 ano."],
         "correta": "B"},
        {"pergunta": "O peculato (art. 312 do CP) é crime praticado por:",
         "alternativas": ["A) Qualquer pessoa.", "B) Funcionário público que se apropria de bem de que tem posse em razão do cargo.", "C) Apenas militares.", "D) Apenas menores.", "E) Apenas estrangeiros."],
         "correta": "B"},
        {"pergunta": "A corrupção passiva (art. 317 do CP) consiste em:",
         "alternativas": ["A) Oferecer vantagem indevida a funcionário público.", "B) Solicitar ou receber vantagem indevida em razão da função.", "C) Praticar violência arbitrária.", "D) Deixar de praticar ato de ofício.", "E) Apropriar-se de bem público."],
         "correta": "B"},
        {"pergunta": "A prevaricação (art. 319 do CP) consiste em:",
         "alternativas": ["A) Receber vantagem indevida.", "B) Deixar de praticar ato de ofício ou praticá-lo contra disposição legal, por interesse pessoal.", "C) Apropriar-se de bem público.", "D) Ofender a honra de alguém.", "E) Subtrair bem alheio."],
         "correta": "B"},
        {"pergunta": "Sobre o erro de tipo (art. 20 do CP), é correto afirmar:",
         "alternativas": ["A) Sempre exclui a culpabilidade.", "B) Exclui o dolo, mas permite punição por culpa quando previsto em lei.", "C) Nunca exclui o dolo.", "D) Apenas atenua a pena.", "E) Só se aplica a crimes militares."],
         "correta": "B"},
    ],
    "Direito Processual Penal Comum": [
        {"pergunta": "Sobre o inquérito policial, é correto afirmar:",
         "alternativas": ["A) É contraditório e permite ampla defesa.", "B) É peça de natureza inquisitiva e dispensável para a ação penal.", "C) Só pode ser instaurado por ordem do juiz.", "D) Pode ser arquivado pelo delegado.", "E) Não pode ser instaurado de ofício pela autoridade policial."],
         "correta": "B"},
        {"pergunta": "A prisão em flagrante (art. 302 do CPP) ocorre quando o agente é surpreendido:",
         "alternativas": ["A) Somente cometendo o fato.", "B) Cometendo o fato, acabando de cometê-lo ou sendo perseguido logo após.", "C) Só após a sentença condenatória.", "D) Somente em crimes hediondos.", "E) Apenas após a denúncia."],
         "correta": "B"},
        {"pergunta": "Sobre as provas ilícitas no processo penal, é correto afirmar:",
         "alternativas": ["A) São válidas se corroboradas por outras provas.", "B) São inadmissíveis, salvo quando puderem ser obtidas por fonte independente.", "C) Não há previsão legal sobre o tema.", "D) São admissíveis se o juiz entender pertinentes.", "E) Só são inválidas em crimes hediondos."],
         "correta": "B"},
        {"pergunta": "A prisão preventiva (art. 312 do CPP) pode ser decretada para:",
         "alternativas": ["A) Garantir a ordem pública, a ordem econômica, por conveniência da instrução ou para assegurar a aplicação da lei penal.", "B) Apenas em crimes hediondos.", "C) Apenas durante o inquérito policial.", "D) Apenas em crimes contra o patrimônio.", "E) Apenas por requerimento do Ministério Público."],
         "correta": "A"},
        {"pergunta": "A ação penal pública incondicionada é aquela que:",
         "alternativas": ["A) Depende de representação da vítima.", "B) Depende de requisição do Ministro da Justiça.", "C) É promovida pelo Ministério Público de ofício, sem condições.", "D) Só pode ser promovida pela vítima.", "E) É promovida por qualquer cidadão."],
         "correta": "C"},
        {"pergunta": "A ação penal privada é promovida:",
         "alternativas": ["A) Pelo Ministério Público.", "B) Pelo ofendido ou seu representante legal, mediante queixa-crime.", "C) Pelo juiz.", "D) Pelo delegado.", "E) Pelo Governador."],
         "correta": "B"},
        {"pergunta": "A denúncia é a peça inicial da:",
         "alternativas": ["A) Ação penal privada.", "B) Ação penal pública.", "C) Ação civil.", "D) Ação trabalhista.", "E) Ação administrativa."],
         "correta": "B"},
        {"pergunta": "Sobre a competência do Tribunal do Júri, é correto afirmar que julga:",
         "alternativas": ["A) Todos os crimes.", "B) Crimes dolosos contra a vida.", "C) Apenas crimes culposos.", "D) Apenas crimes militares.", "E) Apenas crimes eleitorais."],
         "correta": "B"},
        {"pergunta": "A nulidade absoluta no processo penal:",
         "alternativas": ["A) Pode ser sanada.", "B) Não pode ser sanada, por atingir interesse público.", "C) Só existe em crimes hediondos.", "D) Não há previsão legal.", "E) É sempre relativa."],
         "correta": "B"},
        {"pergunta": "A citação no processo penal é o ato pelo qual:",
         "alternativas": ["A) O juiz profere sentença.", "B) O réu é chamado a juízo para se defender.", "C) A vítima é ouvida.", "D) A prova é produzida.", "E) O recurso é interposto."],
         "correta": "B"},
        {"pergunta": "O habeas corpus pode ser impetrado:",
         "alternativas": ["A) Apenas por advogado.", "B) Apenas pelo Ministério Público.", "C) Por qualquer pessoa, física ou jurídica, em favor próprio ou de terceiro.", "D) Apenas pelo réu.", "E) Apenas pelo juiz."],
         "correta": "C"},
        {"pergunta": "A apelação no processo penal é cabível contra:",
         "alternativas": ["A) Apenas despachos.", "B) Sentenças e algumas decisões interlocutórias.", "C) Apenas decisões do STF.", "D) Apenas atos do delegado.", "E) Apenas atos do MP."],
         "correta": "B"},
        {"pergunta": "A revisão criminal pode ser proposta:",
         "alternativas": ["A) Apenas pelo réu.", "B) Apenas pelo MP.", "C) Pelo próprio condenado, pelo MP ou por qualquer pessoa, em favor do condenado.", "D) Apenas por advogado.", "E) Apenas pelo juiz."],
         "correta": "C"},
        {"pergunta": "Sobre a prisão temporária, é correto afirmar:",
         "alternativas": ["A) Não tem prazo definido.", "B) Tem prazo de 5 dias, prorrogável por mais 5, em regra.", "C) Tem prazo de 30 dias.", "D) Só se aplica a crimes culposos.", "E) Só pode ser decretada pelo delegado."],
         "correta": "B"},
        {"pergunta": "A audiência de custódia tem por finalidade:",
         "alternativas": ["A) Julgar o mérito da causa.", "B) Apresentar o preso ao juiz em até 24 horas para avaliar a legalidade da prisão.", "C) Realizar perícia.", "D) Ouvir testemunhas.", "E) Interrogar o réu."],
         "correta": "B"},
    ],
    "Direito Penal Militar": [
        {"pergunta": "O crime de deserção (art. 187 do CPM) configura-se quando o militar:",
         "alternativas": ["A) Deixa de comparecer à unidade por mais de 8 dias.", "B) Ausenta-se sem licença por mais de 24 horas.", "C) Deixa de cumprir ordem superior.", "D) Falta ao serviço embriagado.", "E) Recusa-se a prestar continência."],
         "correta": "A"},
        {"pergunta": "O crime de insubordinação (art. 163 do CPM) consiste em:",
         "alternativas": ["A) Desrespeitar superior hierárquico.", "B) Recusar-se a obedecer ordem legal.", "C) Promover reunião não autorizada.", "D) Deixar de se apresentar ao serviço.", "E) Dormir em serviço."],
         "correta": "B"},
        {"pergunta": "Sobre a competência para julgar crimes militares, é correto afirmar:",
         "alternativas": ["A) Todos os crimes praticados por militares são julgados pela Justiça Militar.", "B) Compete à Justiça Militar processar e julgar os crimes militares definidos em lei.", "C) A Justiça Comum julga todos os crimes militares.", "D) Compete ao STF julgar crimes militares em primeira instância.", "E) A Justiça Militar julga apenas crimes de guerra."],
         "correta": "B"},
        {"pergunta": "O crime de motim (art. 149 do CPM) ocorre quando:",
         "alternativas": ["A) Militares se reúnem para reivindicar direitos.", "B) Militares se reúnem de forma ilegal, com violência ou ameaça, contra a ordem.", "C) Militares desertam.", "D) Militares dormem em serviço.", "E) Militares desrespeitam superior."],
         "correta": "B"},
        {"pergunta": "O crime de revolta (art. 149 do CPM) diferencia-se do motim por:",
         "alternativas": ["A) Ser menos grave.", "B) Envolver maior número de militares e uso de armas, com objetivo de depor autoridades.", "C) Ser crime culposo.", "D) Não existir no CPM.", "E) Ser crime civil."],
         "correta": "B"},
        {"pergunta": "Sobre os crimes propriamente militares, é correto afirmar:",
         "alternativas": ["A) Só podem ser cometidos por civis.", "B) Só podem ser cometidos por militares.", "C) Podem ser cometidos por qualquer pessoa.", "D) Não existem no CPM.", "E) Só existem em tempo de guerra."],
         "correta": "B"},
        {"pergunta": "Os crimes impropriamente militares são aqueles que:",
         "alternativas": ["A) Só podem ser cometidos por militares.", "B) Podem ser cometidos por militares ou civis, mas são considerados militares em razão da função.", "C) Só existem em tempo de paz.", "D) Não existem no CPM.", "E) Só existem em tempo de guerra."],
         "correta": "B"},
        {"pergunta": "O crime de abandono de posto (art. 195 do CPM) consiste em:",
         "alternativas": ["A) Deixar o militar o posto por necessidade de serviço.", "B) Deixar o militar, sem ordem ou autorização, o posto que lhe foi confiado.", "C) Deixar o militar de comparecer ao quartel.", "D) Desrespeitar superior.", "E) Dormir em serviço."],
         "correta": "B"},
        {"pergunta": "O crime de violência contra superior (art. 157 do CPM) consiste em:",
         "alternativas": ["A) Desrespeitar verbalmente superior.", "B) Praticar violência física contra superior.", "C) Recusar obediência.", "D) Deixar de se apresentar.", "E) Dormir em serviço."],
         "correta": "B"},
        {"pergunta": "O crime de embriaguez em serviço (art. 202 do CPM) configura-se quando o militar:",
         "alternativas": ["A) Bebe em serviço, ainda que não fique embriagado.", "B) Apresenta-se embriagado ou se embriaga em serviço.", "C) Bebe fora do serviço.", "D) Recusa-se a beber.", "E) Dorme em serviço."],
         "correta": "B"},
        {"pergunta": "O crime de dormir em serviço (art. 203 do CPM) ocorre quando:",
         "alternativas": ["A) O militar dorme apenas durante o dia.", "B) O militar dorme em serviço, ainda que não esteja em posto de vigilância.", "C) O militar dorme em casa.", "D) O militar dorme em férias.", "E) O militar dorme após o expediente."],
         "correta": "B"},
        {"pergunta": "O crime de homicídio simples militar (art. 205 do CPM) tem pena:",
         "alternativas": ["A) Maior que o homicídio simples comum.", "B) Menor que o homicídio simples comum.", "C) Igual ao homicídio simples comum.", "D) Não existe no CPM.", "E) É apenas infração disciplinar."],
         "correta": "C"},
        {"pergunta": "Sobre a Justiça Militar da União, é correto afirmar:",
         "alternativas": ["A) Julga todos os crimes cometidos por militares.", "B) Julga os crimes militares definidos em lei, praticados por militares federais.", "C) Julga crimes civis em geral.", "D) Não existe no Brasil.", "E) Substitui a Justiça Comum."],
         "correta": "B"},
        {"pergunta": "Sobre a Justiça Militar Estadual, é correto afirmar:",
         "alternativas": ["A) Julga crimes comuns em geral.", "B) Julga os crimes militares praticados por militares estaduais.", "C) Não existe no Brasil.", "D) Substitui a Justiça Comum.", "E) Julga crimes eleitorais."],
         "correta": "B"},
        {"pergunta": "O crime de conspiração (art. 152 do CPM) ocorre quando:",
         "alternativas": ["A) Militares se reúnem para tratar de assuntos particulares.", "B) Militares se reúnem para cometer crime militar.", "C) Militares desertam.", "D) Militares dormem em serviço.", "E) Militares desrespeitam superior."],
         "correta": "B"},
    ],
    "Legislação Especial": [
        {"pergunta": "Conforme a Lei nº 11.343/2006 (Lei de Drogas), o porte de drogas para consumo pessoal:",
         "alternativas": ["A) Sujeita o agente a pena privativa de liberdade.", "B) Sujeita o agente a advertência, prestação de serviços e medida educativa.", "C) Não tem qualquer consequência legal.", "D) Equipara-se ao tráfico.", "E) Só é punido se o agente for reincidente."],
         "correta": "B"},
        {"pergunta": "Sobre o Estatuto do Desarmamento (Lei nº 10.826/2003), é correto afirmar:",
         "alternativas": ["A) Permite o porte de arma em todo território nacional.", "B) Criminaliza o porte ilegal de arma de fogo de uso permitido.", "C) Proíbe qualquer registro de arma de fogo.", "D) Só se aplica a militares.", "E) Revogou todos os crimes de porte de arma."],
         "correta": "B"},
        {"pergunta": "A Lei Maria da Penha (Lei nº 11.340/2006) tem como finalidade:",
         "alternativas": ["A) Regulamentar o casamento civil.", "B) Criar mecanismos para coibir e prevenir a violência doméstica e familiar contra a mulher.", "C) Punir apenas o homicídio de mulheres.", "D) Disciplinar o divórcio.", "E) Estabelecer cota de gênero em empresas."],
         "correta": "B"},
        {"pergunta": "Sobre o ECA (Lei nº 8.069/1990), é correto afirmar:",
         "alternativas": ["A) Considera criança a pessoa até 12 anos incompletos e adolescente entre 12 e 18 anos.", "B) Considera criança até 14 anos.", "C) Só se aplica a maiores de 12 anos.", "D) Substituiu o Código Penal.", "E) Revogou a proteção integral."],
         "correta": "A"},
        {"pergunta": "A Lei nº 9.455/1997 define o crime de tortura. Sobre ele, é correto afirmar:",
         "alternativas": ["A) Só se aplica a agentes públicos.", "B) Pode ser cometido por particular ou agente público, com pena aumentada para este.", "C) Não existe no Brasil.", "D) Só se aplica a militares.", "E) É crime culposo."],
         "correta": "B"},
        {"pergunta": "A Lei nº 8.072/1990 define os crimes hediondos. NÃO é considerado hediondo:",
         "alternativas": ["A) Homicídio qualificado.", "B) Latrocínio.", "C) Estupro.", "D) Furto simples.", "E) Extorsão mediante sequestro."],
         "correta": "D"},
        {"pergunta": "Sobre a Lei de Abuso de Autoridade (Lei nº 13.869/2019), é correto afirmar:",
         "alternativas": ["A) Pune apenas militares.", "B) Pune agentes públicos que abusam de suas atribuições.", "C) Revogou o Código Penal.", "D) Não se aplica a policiais.", "E) Só se aplica a juízes."],
         "correta": "B"},
        {"pergunta": "A Lei nº 12.850/2013 define organização criminosa. Sobre ela, é correto afirmar:",
         "alternativas": ["A) Exige apenas duas pessoas.", "B) Exige quatro ou mais pessoas, estruturalmente ordenadas e com divisão de tarefas, com objetivo de obter vantagem.", "C) Só se aplica a crimes federais.", "D) Não existe no Brasil.", "E) Só se aplica a militares."],
         "correta": "B"},
        {"pergunta": "A Lei nº 9.296/1996 regula:",
         "alternativas": ["A) A interceptação telefônica.", "B) O casamento civil.", "C) O trânsito.", "D) O meio ambiente.", "E) A previdência."],
         "correta": "A"},
        {"pergunta": "A Lei nº 12.737/2012 (Lei Carolina Dieckmann) trata de:",
         "alternativas": ["A) Crimes cibernéticos, como invasão de dispositivos informáticos.", "B) Crimes de trânsito.", "C) Crimes ambientais.", "D) Crimes militares.", "E) Crimes eleitorais."],
         "correta": "A"},
        {"pergunta": "A Lei nº 7.716/1989 define os crimes resultantes de preconceito de raça ou cor. Sobre ela, é correto afirmar:",
         "alternativas": ["A) O racismo é crime imprescritível e inafiançável.", "B) O racismo é crime prescritível.", "C) O racismo não é crime.", "D) Só se aplica a estrangeiros.", "E) Só se aplica a militares."],
         "correta": "A"},
        {"pergunta": "Sobre o Estatuto do Idoso (Lei nº 10.741/2003), é correto afirmar:",
         "alternativas": ["A) Considera idosa a pessoa com 60 anos ou mais.", "B) Considera idosa a pessoa com 70 anos ou mais.", "C) Só se aplica a maiores de 80 anos.", "D) Não existe no Brasil.", "E) Revogou o ECA."],
         "correta": "A"},
        {"pergunta": "A Lei Brasileira de Inclusão (Lei nº 13.146/2015) trata:",
         "alternativas": ["A) Dos direitos da pessoa com deficiência.", "B) Dos direitos do consumidor.", "C) Do trânsito.", "D) Do meio ambiente.", "E) Dos crimes militares."],
         "correta": "A"},
        {"pergunta": "A Lei nº 13.709/2018 (LGPD) trata de:",
         "alternativas": ["A) Proteção de dados pessoais.", "B) Licitações.", "C) Improbidade administrativa.", "D) Crimes militares.", "E) Trânsito."],
         "correta": "A"},
        {"pergunta": "O Marco Civil da Internet (Lei nº 12.965/2014) estabelece princípios, garantias, direitos e deveres para o uso da Internet no Brasil. NÃO é um de seus princípios:",
         "alternativas": ["A) Liberdade de expressão.", "B) Proteção da privacidade.", "C) Neutralidade da rede.", "D) Censura prévia.", "E) Preservação da estabilidade e segurança da rede."],
         "correta": "D"},
        {"pergunta": "A Lei nº 13.260/2016 (Lei Antiterrorismo) define terrorismo como:",
         "alternativas": ["A) Qualquer manifestação política.", "B) A prática de atos por razões de xenofobia, discriminação ou preconceito, com objetivo de provocar terror social ou generalizado.", "C) Qualquer crime violento.", "D) Apenas crimes militares.", "E) Apenas crimes cibernéticos."],
         "correta": "B"},
    ],
    "Legislação de Trânsito": [
        {"pergunta": "Sobre o crime de homicídio culposo na direção de veículo automotor (art. 302 do CTB), é correto afirmar:",
         "alternativas": ["A) A pena é aumentada se o motorista não prestar socorro à vítima.", "B) Só se aplica a motoristas profissionais.", "C) Exige dolo eventual.", "D) Não admite agravantes.", "E) A pena é a mesma do homicídio doloso."],
         "correta": "A"},
        {"pergunta": "Conforme o CTB, a CNH será suspensa quando o condutor atingir, em 12 meses:",
         "alternativas": ["A) 10 pontos.", "B) 20 pontos, com exceções legais, 30 ou 40 pontos conforme o caso.", "C) 50 pontos.", "D) 5 pontos.", "E) Nenhuma pontuação suspende a CNH."],
         "correta": "B"},
        {"pergunta": "Sobre as infrações de trânsito, é correto afirmar:",
         "alternativas": ["A) As infrações leves geram 3 pontos na CNH.", "B) As infrações gravíssimas geram 7 pontos na CNH.", "C) Todas as infrações têm o mesmo valor de multa.", "D) O condutor não pode recorrer de multas.", "E) As infrações médias geram 10 pontos."],
         "correta": "B"},
        {"pergunta": "O CTB (Lei nº 9.503/1997) define trânsito como:",
         "alternativas": ["A) Apenas a circulação de veículos.", "B) A utilização das vias por pessoas, veículos e animais, isolados ou em grupos, conduzidos ou não, para fins de circulação, parada, estacionamento e operação de carga ou descarga.", "C) Apenas a circulação de pedestres.", "D) Apenas a circulação de animais.", "E) Apenas a circulação de bicicletas."],
         "correta": "B"},
        {"pergunta": "São vias urbanas, conforme o CTB:",
         "alternativas": ["A) Apenas rodovias.", "B) Vias de trânsito rápido, arteriais, coletoras e locais.", "C) Apenas estradas.", "D) Apenas ciclovias.", "E) Apenas calçadas."],
         "correta": "B"},
        {"pergunta": "São vias rurais, conforme o CTB:",
         "alternativas": ["A) Rodovias e estradas.", "B) Apenas ruas.", "C) Apenas avenidas.", "D) Apenas ciclovias.", "E) Apenas calçadas."],
         "correta": "A"},
        {"pergunta": "Sobre o uso do cinto de segurança, é correto afirmar:",
         "alternativas": ["A) É facultativo.", "B) É obrigatório para todos os ocupantes do veículo.", "C) Só é obrigatório para o motorista.", "D) Só é obrigatório em rodovias.", "E) Só é obrigatório para maiores de idade."],
         "correta": "B"},
        {"pergunta": "Sobre a embriaguez ao volante (art. 165 e 306 do CTB), é correto afirmar:",
         "alternativas": ["A) Não há tolerância.", "B) É infração gravíssima e crime, com tolerância zero para álcool no organismo.", "C) É permitido dirigir após uma dose.", "D) Só é crime em rodovias.", "E) Só é infração administrativa."],
         "correta": "B"},
        {"pergunta": "A recusa ao teste do bafômetro (art. 165-A do CTB) é:",
         "alternativas": ["A) Permitida, sem consequências.", "B) Infração gravíssima, com multa e suspensão do direito de dirigir.", "C) Apenas advertência.", "D) Crime.", "E) Facultativa."],
         "correta": "B"},
        {"pergunta": "As categorias de habilitação no Brasil incluem:",
         "alternativas": ["A) Apenas A e B.", "B) A, B, C, D e E, conforme o tipo de veículo.", "C) Apenas A.", "D) Apenas B.", "E) Apenas C e D."],
         "correta": "B"},
        {"pergunta": "A Permissão Para Dirigir (PPD) tem validade de:",
         "alternativas": ["A) 1 ano.", "B) 2 anos.", "C) 5 anos.", "D) 10 anos.", "E) Indeterminada."],
         "correta": "A"},
        {"pergunta": "A CNH tem validade, em regra, de:",
         "alternativas": ["A) 1 ano.", "B) 5 anos, podendo variar conforme a idade do condutor.", "C) 10 anos para todos.", "D) 20 anos.", "E) Indeterminada."],
         "correta": "B"},
        {"pergunta": "A suspensão do direito de dirigir difere da cassação porque:",
         "alternativas": ["A) São sinônimos.", "B) Suspensão é temporária; cassação é definitiva, exigindo novo processo de habilitação.", "C) Suspensão é definitiva.", "D) Cassação é temporária.", "E) Nenhuma das anteriores."],
         "correta": "B"},
        {"pergunta": "São equipamentos obrigatórios dos veículos, entre outros:",
         "alternativas": ["A) Cinto de segurança, extintor, triângulo.", "B) Apenas cinto.", "C) Apenas extintor.", "D) Apenas triângulo.", "E) Nenhum."],
         "correta": "A"},
        {"pergunta": "Sobre a velocidade máxima nas vias urbanas, é correto afirmar que:",
         "alternativas": ["A) É sempre 60 km/h.", "B) Varia conforme a classificação da via, podendo chegar a 80 km/h em vias de trânsito rápido.", "C) É sempre 40 km/h.", "D) É sempre 100 km/h.", "E) Não há limite."],
         "correta": "B"},
        {"pergunta": "O condutor que dirige sem possuir CNH ou PPD comete:",
         "alternativas": ["A) Apenas infração leve.", "B) Infração gravíssima e crime de trânsito (art. 309 do CTB).", "C) Apenas advertência.", "D) Infração média.", "E) Nada, se maior de idade."],
         "correta": "B"},
    ],
    "Informática": [
        {"pergunta": "No Microsoft Excel, a função que soma um intervalo de células é:",
         "alternativas": ["A) =MÉDIA()", "B) =SOMA()", "C) =CONTAR()", "D) =MÁXIMO()", "E) =SE()"],
         "correta": "B"},
        {"pergunta": "Sobre segurança da informação, o termo 'phishing' refere-se a:",
         "alternativas": ["A) Golpe que tenta obter dados pessoais por meio de mensagens falsas.", "B) Técnica de backup em nuvem.", "C) Protocolo de segurança de rede.", "D) Método de criptografia de disco.", "E) Tipo de firewall."],
         "correta": "A"},
        {"pergunta": "No Windows 11, o atalho 'Ctrl + Shift + Esc' abre:",
         "alternativas": ["A) O explorador de arquivos.", "B) O gerenciador de tarefas.", "C) A calculadora.", "D) O prompt de comando.", "E) As configurações do sistema."],
         "correta": "B"},
        {"pergunta": "Sobre a Internet, é correto afirmar que o protocolo HTTPS:",
         "alternativas": ["A) É mais lento e inseguro que o HTTP.", "B) Utiliza criptografia para proteger a comunicação.", "C) Não é usado por navegadores.", "D) Substituiu o DNS.", "E) É exclusivo de intranets."],
         "correta": "B"},
        {"pergunta": "No Microsoft Word, o atalho 'Ctrl + B' (ou 'Ctrl + N' em algumas versões) serve para:",
         "alternativas": ["A) Salvar o documento.", "B) Negritar o texto selecionado.", "C) Copiar o texto.", "D) Colar o texto.", "E) Imprimir o documento."],
         "correta": "B"},
        {"pergunta": "No Excel, a função =MÉDIA(A1:A10) retorna:",
         "alternativas": ["A) A soma das células.", "B) A média aritmética das células.", "C) O maior valor.", "D) O menor valor.", "E) A contagem das células."],
         "correta": "B"},
        {"pergunta": "No Excel, a função =SE(A1>10;'Aprovado';'Reprovado') serve para:",
         "alternativas": ["A) Somar valores.", "B) Realizar um teste lógico condicional.", "C) Contar células.", "D) Multiplicar valores.", "E) Arredondar valores."],
         "correta": "B"},
        {"pergunta": "No Excel, a função PROCV é utilizada para:",
         "alternativas": ["A) Somar valores.", "B) Procurar um valor em uma coluna e retornar um valor correspondente em outra coluna.", "C) Contar células.", "D) Concatenar textos.", "E) Arredondar valores."],
         "correta": "B"},
        {"pergunta": "No Windows, o atalho 'Ctrl + C' serve para:",
         "alternativas": ["A) Colar.", "B) Copiar.", "C) Recortar.", "D) Salvar.", "E) Imprimir."],
         "correta": "B"},
        {"pergunta": "Sobre o Windows Explorer (Explorador de Arquivos), é correto afirmar que:",
         "alternativas": ["A) Serve apenas para navegar na Internet.", "B) Permite gerenciar arquivos e pastas no computador.", "C) É um antivírus.", "D) É um editor de texto.", "E) É um navegador."],
         "correta": "B"},
        {"pergunta": "São exemplos de navegadores de Internet:",
         "alternativas": ["A) Word e Excel.", "B) Google Chrome, Mozilla Firefox, Microsoft Edge.", "C) Windows e Linux.", "D) Word e PowerPoint.", "E) Photoshop e Illustrator."],
         "correta": "B"},
        {"pergunta": "Sobre o backup, é correto afirmar:",
         "alternativas": ["A) É dispensável.", "B) É uma cópia de segurança dos dados, importante para recuperação em caso de perda.", "C) Só existe em nuvem.", "D) Só existe em HD externo.", "E) Nunca deve ser feito."],
         "correta": "B"},
        {"pergunta": "Sobre vírus e worms, é correto afirmar:",
         "alternativas": ["A) São sinônimos.", "B) Vírus precisa de um hospedeiro para se propagar; worm se propaga sozinho pela rede.", "C) Worm precisa de hospedeiro.", "D) Vírus não existe.", "E) Worm não existe."],
         "correta": "B"},
        {"pergunta": "O firewall tem como função:",
         "alternativas": ["A) Aumentar a velocidade da Internet.", "B) Filtrar o tráfego de rede, bloqueando acessos não autorizados.", "C) Armazenar arquivos.", "D) Editar textos.", "E) Reproduzir vídeos."],
         "correta": "B"},
        {"pergunta": "São exemplos de serviços de armazenamento em nuvem:",
         "alternativas": ["A) Word e Excel.", "B) Google Drive, OneDrive, Dropbox.", "C) Chrome e Firefox.", "D) Windows e Linux.", "E) Photoshop e Illustrator."],
         "correta": "B"},
        {"pergunta": "Um endereço IP (Internet Protocol) serve para:",
         "alternativas": ["A) Identificar um dispositivo em uma rede.", "B) Armazenar arquivos.", "C) Editar textos.", "D) Reproduzir vídeos.", "E) Imprimir documentos."],
         "correta": "A"},
        {"pergunta": "Uma URL (Uniform Resource Locator) é:",
         "alternativas": ["A) Um tipo de vírus.", "B) O endereço de um recurso na Internet.", "C) Um programa de edição.", "D) Um tipo de firewall.", "E) Um serviço de e-mail."],
         "correta": "B"},
        {"pergunta": "Cookies são:",
         "alternativas": ["A) Pequenos arquivos armazenados pelo navegador com informações de navegação.", "B) Vírus.", "C) Programas de edição.", "D) Serviços de e-mail.", "E) Tipos de firewall."],
         "correta": "A"},
    ],
}

# ==================================================================
# FUNÇÕES AUXILIARES
# ==================================================================
def montar_simulado():
    todas = []
    for materia, qtd in DISTRIBUICAO.items():
        disponiveis = BANCO_QUESTOES.get(materia, [])
        if not disponiveis:
            continue
        if len(disponiveis) >= qtd:
            selecionadas = random.sample(disponiveis, qtd)
        else:
            selecionadas = disponiveis + random.choices(disponiveis, k=qtd - len(disponiveis))
        for q in selecionadas:
            qc = json.loads(json.dumps(q))
            qc["materia"] = materia
            todas.append(qc)
    return todas

def render_3d(questoes, modo="treino"):
    questoes_json = json.dumps(questoes, ensure_ascii=False)
    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <style>body{{margin:0;overflow:hidden;background:#0a0a1a}}canvas{{display:block}}</style>
    </head><body>
    <script type="importmap">
    {{"imports":{{
      "three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
      "three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
    }}}}
    </script>
    <script type="module">
    import * as THREE from 'three';
    import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';
    import {{ VRButton }} from 'three/addons/webxr/VRButton.js';
    const questoes = {questoes_json};
    const modo = "{modo}";
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a1a);
    scene.fog = new THREE.Fog(0x0a0a1a, 15, 70);
    const camera = new THREE.PerspectiveCamera(60, window.innerWidth/window.innerHeight, 0.1, 1000);
    camera.position.set(0, 6, 14);
    const renderer = new THREE.WebGLRenderer({{ antialias: true }});
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.xr.enabled = true;
    document.body.appendChild(renderer.domElement);
    document.body.appendChild(VRButton.createButton(renderer));
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(0, 3, 0);
    scene.add(new THREE.AmbientLight(0x404070, 1.2));
    const dir = new THREE.DirectionalLight(0xffffff, 2);
    dir.position.set(8, 15, 10); dir.castShadow = true; scene.add(dir);
    const p1 = new THREE.PointLight(0x0066ff, 60, 30);
    p1.position.set(-8, 8, 8); scene.add(p1);
    const p2 = new THREE.PointLight(0xff6600, 30, 25);
    p2.position.set(8, 4, -8); scene.add(p2);
    const grid = new THREE.GridHelper(50, 50, 0x0066cc, 0x1a1a3a);
    grid.position.y = -0.5; scene.add(grid);
    const group = new THREE.Group(); scene.add(group);
    function criarCartao(q, index) {{
      const canvas = document.createElement('canvas');
      canvas.width = 512; canvas.height = 512;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#12122a'; ctx.fillRect(0,0,512,512);
      ctx.strokeStyle = modo==='simulado' ? '#ff6600' : '#0066cc';
      ctx.lineWidth = 6; ctx.strokeRect(3,3,506,506);
      ctx.fillStyle = modo==='simulado' ? '#ff8844' : '#4488ff';
      ctx.font = 'bold 16px "Segoe UI"';
      ctx.fillText(q.materia || 'Treino', 25, 35);
      ctx.fillStyle = '#ffffff'; ctx.font = 'bold 21px "Segoe UI"';
      const palavras = q.pergunta.split(' ');
      let linha='', y=75;
      for (const p of palavras) {{
        const teste = linha+p+' ';
        if (ctx.measureText(teste).width > 460) {{
          ctx.fillText(linha, 25, y); linha = p+' '; y += 28;
        }} else {{ linha = teste; }}
      }}
      ctx.fillText(linha, 25, y);
      ctx.font = '17px "Segoe UI"'; ctx.fillStyle = '#bbbbdd';
      y += 40;
      q.alternativas.forEach(a => {{ ctx.fillText(a, 35, y); y += 28; }});
      ctx.fillStyle = '#555577'; ctx.font = '14px "Segoe UI"';
      ctx.fillText(modo==='simulado' ? '👆 Clique para responder' : '👆 Clique para revelar', 25, 480);
      const tex = new THREE.CanvasTexture(canvas);
      const mat = new THREE.MeshStandardMaterial({{
        map: tex, roughness: 0.4, metalness: 0.1,
        emissive: new THREE.Color(modo==='simulado'?0x331100:0x001133),
        emissiveIntensity: 0.15
      }});
      const card = new THREE.Mesh(new THREE.BoxGeometry(4,4,0.15), mat);
      card.castShadow = true; card.receiveShadow = true;
      const cols = 3;
      const x = (index%cols)*4.8 - (cols-1)*2.4;
      const z = Math.floor(index/cols)*4.8;
      card.position.set(x, 2.2, -z);
      card.userData = {{ virado:false }};
      card.addEventListener('click', () => {{
        if (modo !== 'treino') return;
        if (!card.userData.virado) {{
          const c2 = document.createElement('canvas');
          c2.width=512; c2.height=512;
          const x2 = c2.getContext('2d');
          x2.fillStyle='#0a2a1a'; x2.fillRect(0,0,512,512);
          x2.strokeStyle='#00cc66'; x2.lineWidth=6; x2.strokeRect(3,3,506,506);
          x2.fillStyle='#fff'; x2.font='bold 34px "Segoe UI"'; x2.textAlign='center';
          x2.fillText('✅ Resposta', 256, 180);
          x2.font='bold 80px "Segoe UI"'; x2.fillStyle='#00ff88';
          x2.fillText(q.correta, 256, 290);
          const nt = new THREE.CanvasTexture(c2);
          card.material.map = nt; card.material.needsUpdate = true;
          card.userData.virado = true;
        }} else {{
          card.material.map = tex; card.material.needsUpdate = true;
          card.userData.virado = false;
        }}
      }});
      return card;
    }}
    questoes.forEach((q,i) => group.add(criarCartao(q,i)));
    const linhas = Math.ceil(questoes.length/3);
    controls.target.set(0, 2, -((linhas-1)*4.8)/2);
    camera.position.set(0, Math.max(8, linhas*3.5), linhas*3.5 + 6);
    renderer.setAnimationLoop(() => {{
      controls.update(); renderer.render(scene, camera);
    }});
    window.addEventListener('resize', () => {{
      camera.aspect = window.innerWidth/window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    }});
    </script></body></html>
    """
    components.html(html, height=650, scrolling=False)

# ==================================================================
# SESSION STATE
# ==================================================================
for key, default in [("questoes_treino", []), ("simulado", None), ("historico", [])]:
    if key not in st.session_state:
        st.session_state[key] = default

# ==================================================================
# BARRA LATERAL
# ==================================================================
with st.sidebar:
    st.title("🎯 PMSC 3D")
    st.caption("Banca: Instituto AOCP")
    st.divider()
    st.subheader("📚 Treino por Matéria")
    materia = st.selectbox("Matéria", list(BANCO_QUESTOES.keys()), key="mat_sel")
    maximo = len(BANCO_QUESTOES[materia])
    qtd = st.number_input("Quantidade", min_value=1, max_value=maximo,
                          value=min(5, maximo), key="qtd_sel")
    if st.button("Gerar Questões de Treino", type="primary", use_container_width=True):
        selecionadas = random.sample(BANCO_QUESTOES[materia], qtd)
        questoes = []
        for q in selecionadas:
            qc = json.loads(json.dumps(q))
            qc["materia"] = materia
            questoes.append(qc)
        st.session_state.questoes_treino = questoes
        st.session_state.simulado = None
        st.success(f"✅ {len(questoes)} questões carregadas.")
    st.divider()
    st.subheader("📝 Simulado Completo")
    st.caption(f"{TOTAL} questões na proporção oficial do edital.")
    if st.button("Iniciar Simulado", use_container_width=True):
        st.session_state.simulado = {
            "questoes": montar_simulado(),
            "inicio": time.time(),
            "respostas": {},
            "finalizado": False,
        }
        st.session_state.questoes_treino = []
        st.success("✅ Simulado iniciado.")
        st.rerun()
    if st.session_state.simulado and not st.session_state.simulado["finalizado"]:
        if st.button("❌ Cancelar Simulado", use_container_width=True):
            st.session_state.simulado = None
            st.rerun()
    st.divider()
    st.subheader("✍️ Redação")
    with st.expander("Abrir módulo"):
        tema = st.text_input("Tema", key="red_tema")
        redacao = st.text_area("Sua redação", height=280, key="red_txt")
        if st.button("Analisar Redação", use_container_width=True):
            if not tema.strip() or not redacao.strip():
                st.warning("Preencha tema e redação.")
            else:
                linhas = len([l for l in redacao.split("\n") if l.strip()])
                palavras = len(redacao.split())
                paragrafos = len([p for p in redacao.split("\n\n") if p.strip()])
                st.markdown("**📊 Análise estrutural**")
                st.metric("Linhas", linhas)
                st.metric("Palavras", palavras)
                st.metric("Parágrafos", paragrafos)
                if 20 <= linhas <= 30:
                    st.success("✅ Extensão adequada ao edital.")
                else:
                    st.warning(f"A redação deve ter 20–30 linhas. Atual: {linhas}.")
                if paragrafos < 3:
                    st.info("Recomendado: introdução, desenvolvimento e conclusão.")

# ==================================================================
# ÁREA PRINCIPAL
# ==================================================================
st.title("🎯 PMSC – Estudo 3D Imersivo")
st.caption("Questões estilo AOCP | Visualização 3D | Meta Quest 3S (WebXR)")

if st.session_state.simulado:
    sim = st.session_state.simulado
    questoes = sim["questoes"]
    if not sim["finalizado"]:
        restante = max(0, 4 * 3600 - int(time.time() - sim["inicio"]))
        h, m, s = restante // 3600, (restante % 3600) // 60, restante % 60
        st.warning(f"⏱️ **Tempo restante:** {h:02d}:{m:02d}:{s:02d}")
        st.subheader("🌐 Visualização 3D")
        render_3d(questoes, modo="simulado")
        st.subheader("✍️ Responda as Questões")
        with st.form("form_sim"):
            respostas = {}
            for i, q in enumerate(questoes):
                st.markdown(f"**{i+1}. [{q.get('materia','')}]** {q['pergunta']}")
                escolha = st.radio(f"q_{i}", options=q["alternativas"], index=None,
                                   key=f"sim_q_{i}", label_visibility="collapsed")
                if escolha:
                    respostas[i] = escolha[0].upper()
                st.divider()
            c1, c2 = st.columns(2)
            salvar = c1.form_submit_button("💾 Salvar Respostas", use_container_width=True)
            finalizar = c2.form_submit_button("✅ Finalizar Simulado", type="primary", use_container_width=True)
            if salvar:
                sim["respostas"] = respostas
                st.success("Respostas salvas.")
                st.rerun()
            if finalizar:
                acertos, detalhes = 0, []
                for i, q in enumerate(questoes):
                    r = respostas.get(i, "")
                    correta = q["correta"].upper()
                    ok = r == correta
                    if ok: acertos += 1
                    detalhes.append({"pergunta": q["pergunta"], "materia": q.get("materia",""),
                                     "resposta": r, "correta": correta, "acertou": ok})
                nota = (acertos / len(questoes)) * 100
                st.session_state.historico.append({
                    "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "acertos": acertos, "total": len(questoes),
                    "nota": round(nota, 2), "aprovado": nota >= 50,
                    "detalhes": detalhes, "tempo": time.time() - sim["inicio"],
                })
                sim["finalizado"] = True
                st.rerun()
    else:
        ultimo = st.session_state.historico[-1] if st.session_state.historico else None
        if ultimo:
            st.subheader("📊 Resultado do Simulado")
            c1, c2, c3 = st.columns(3)
            c1.metric("Nota", f"{ultimo['nota']}%")
            c2.metric("Acertos", f"{ultimo['acertos']} / {ultimo['total']}")
            c3.metric("Status", "✅ APROVADO" if ultimo["aprovado"] else "❌ REPROVADO")
            st.caption(f"Tempo: {int(ultimo['tempo']//60)} min | Data: {ultimo['data']}")
            with st.expander("Ver detalhes por questão"):
                for i, d in enumerate(ultimo["detalhes"]):
                    icon = "✅" if d["acertou"] else "❌"
                    st.markdown(f"{icon} **{i+1}. [{d['materia']}]** {d['pergunta']}")
                    st.caption(f"Sua resposta: {d['resposta'] or '—'} | Correta: {d['correta']}")
        if st.button("Novo Simulado"):
            st.session_state.simulado = None
            st.rerun()

elif st.session_state.questoes_treino:
    mat = st.session_state.questoes_treino[0].get("materia", "Treino")
    st.subheader(f"🌐 Visualização 3D – {mat}")
    render_3d(st.session_state.questoes_treino, modo="treino")
    st.subheader("📖 Questões (texto)")
    for i, q in enumerate(st.session_state.questoes_treino):
        with st.expander(f"Questão {i+1}"):
            st.markdown(q["pergunta"])
            for alt in q["alternativas"]:
                st.markdown(f"- {alt}")
            st.success(f"Resposta correta: **{q['correta']}**")

else:
    st.info("👈 Use a barra lateral para **gerar treino**, **iniciar simulado** ou **analisar redação**.")
    st.markdown(
        f"""
### 🎯 Sobre o app
- **Banca:** Instituto AOCP – PMSC Soldado
- **Banco com +150 questões** embutido (sem API, sem custo, sem limite)
- **60 questões** por simulado, na proporção oficial
- **Visualização 3D** com WebXR para o Meta Quest 3S
- **Correção automática** com base em 50% de aproveitamento
- **Análise de redação** com métricas estruturais

### 📊 Distribuição do simulado
{chr(10).join(f'- {m}: **{q}** questões' for m, q in DISTRIBUICAO.items())}
        """
    )

if st.session_state.historico:
    with st.sidebar:
        st.divider()
        st.subheader("📜 Histórico")
        for h in reversed(st.session_state.historico[-5:]):
            st.caption(f"{h['data']} – {h['acertos']}/{h['total']} ({h['nota']}%)")
