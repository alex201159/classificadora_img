separador_tampas/
├── PROJETO_SEPARADOR_TAMPAS.md
├── README.md
├── main.py
├── camera/
├── vision/
├── gpio/
├── config/
└── tests/
PROJETO SEPARADOR AUTOMÁTICO DE TAMPAS

1. Objetivo

Desenvolver uma máquina automática para identificar e separar tampas em
uma esteira usando visão computacional.

O sistema deverá: - Capturar imagens das tampas em movimento. - Detectar
a presença de cada tampa. - Classificar as tampas por cor e formato. -
Rastrear a tampa desde a região de inspeção até o ponto de separação. -
Acionar a saída correspondente no momento correto. - Utilizar válvulas
solenoides e jatos de ar para realizar a separação física. - Exibir
status, contadores, câmera e controles em uma interface gráfica
touchscreen. - Operar de forma autônoma após a inicialização.

2. Hardware principal

Computador

Orange Pi 4 Pro

4 GB de RAM

O Orange Pi será o controlador central.

Não utilizar ESP32 como controlador principal.

Câmera, processamento, sensores e acionamentos serão coordenados
pelo Orange Pi.

Sistema operacional

Armbian

Debian 13 Trixie

Kernel vendor da placa

Ambiente gráfico atualmente: Cinnamon

Xorg/LightDM

Display

Tela LCD de 7 polegadas

Painel identificado: DLC0700BIG-1

Resolução física informada para o painel: 800 x 480

A tela está conectada por uma placa controladora universal.

A controladora pode apresentar ao Linux um EDID diferente das
características reais do painel.

Saída gráfica observada no sistema: HDMI-1.

Durante a configuração foram encontrados modos como 1024x768,
1024x600, 800x600 e 640x480.

A resolução e o overscan ainda devem ser refinados para aproveitar
toda a área visível.

3. Arquitetura geral

Fluxo esperado:

Câmera
  |
  v
Captura de imagem
  |
  v
Visão computacional
  |
  +--> Detecção da tampa
  |
  +--> Classificação de cor
  |
  +--> Classificação de formato
  |
  v
Rastreamento / temporização
  |
  v
Determinação da saída
  |
  v
GPIO Orange Pi
  |
  v
Interface de potência isolada
  |
  v
Válvula solenoide
  |
  v
Jato de ar
  |
  v
Tampa direcionada para a saída correta

4. Software

Linguagem principal: - Python 3

Bibliotecas/base inicial: - OpenCV para captura e processamento de
imagem. - NumPy para processamento numérico. - GPIO compatível com
Orange Pi 4 Pro. - Interface gráfica a definir após testes no
equipamento. - ONNX Runtime e/ou YOLO poderão ser adicionados se a
classificação tradicional não for suficiente.

Evitar adicionar inteligência artificial pesada sem necessidade. Para
cores e formas bem definidas, começar com visão computacional clássica e
medir o desempenho.

5. Estratégia de visão computacional

Implementar inicialmente uma solução simples e determinística:

Capturar frame da câmera.

Definir região de interesse (ROI).

Corrigir iluminação/cor quando necessário.

Segmentar a tampa do fundo.

Detectar contorno.

Calcular características geométricas.

Determinar cor.

Determinar formato.

Atribuir um ID à tampa.

Registrar instante/posição da detecção.

Calcular quando a tampa chegará ao ponto do jato de ar.

Acionar a saída correspondente.

Características que podem ser utilizadas: - Área. - Perímetro. -
Circularidade. - Razão largura/altura. - Diâmetro aproximado. - Cor
média. - HSV. - Contorno. - Número de vértices. - Orientação.

Se essas características não forem suficientes, preparar módulo
alternativo usando modelo treinado.

6. Iluminação

A iluminação deve ser tratada como parte do sistema de visão.

Preferir: - Iluminação LED fixa. - Ambiente de inspeção protegido da luz
externa. - Fundo de cor conhecida. - Distância fixa entre câmera e
esteira. - Exposição e balanço de branco da câmera preferencialmente
fixos durante a produção.

Não depender exclusivamente de autoexposição se isso alterar
significativamente a classificação das cores.

7. Sensores

O projeto poderá utilizar sensores para: - Detectar entrada de uma
tampa. - Sincronizar captura. - Confirmar passagem. - Determinar posição
antes do ponto de expulsão. - Detectar obstrução. - Medir velocidade da
esteira, se necessário.

As entradas industriais não devem ser ligadas diretamente aos GPIOs sem
adequação elétrica.

Utilizar interface apropriada, como: - Optoacopladores. -
Divisores/condicionamento quando tecnicamente apropriado. - Proteção
contra transientes. - Filtros contra ruído.

8. Saídas e válvulas

Os GPIOs do Orange Pi NÃO devem alimentar válvulas diretamente.

Arquitetura:

GPIO
  |
  v
Driver / optoacoplador
  |
  v
MOSFET ou estágio de potência
  |
  v
Válvula solenoide 12 V ou 24 V
  |
  v
Jato de ar

Adicionar proteção contra tensão reversa/indutiva nas cargas
apropriadas.

A alimentação das válvulas deve ser separada/adequadamente dimensionada
e não deve sobrecarregar a alimentação do Orange Pi.

9. Temporização da separação

A câmera detectará a tampa antes do ponto de expulsão.

O software deverá relacionar: - posição de detecção; - velocidade da
esteira; - distância até a válvula; - latência do processamento; - tempo
de resposta da válvula; - duração necessária do pulso de ar.

Uma aproximação inicial:

tempo_ate_valvula = distancia / velocidade

O disparo real deverá incluir compensações calibráveis.

Nunca bloquear o processamento principal com longos sleep() para
controlar válvulas. Usar temporização assíncrona, fila de eventos ou
scheduler.

10. Rastreamento

Cada tampa detectada deverá receber um identificador interno.

Exemplo:

ID 105
Classe: vermelha_redonda
Entrada: 14:32:10.125
Saída: valvula_2
Disparo previsto: 14:32:10.842
Estado: aguardando

Isso permite que várias tampas estejam simultaneamente entre a câmera e
os pontos de separação.

11. Interface gráfica

A interface final deverá ser criada para operação industrial em
touchscreen.

Objetivos: - Tela cheia. - Botões grandes. - Alto contraste. - Pouco
texto desnecessário. - Operação simples. - Não exigir que o operador
interaja com o desktop Linux.

Tela principal sugerida: - Estado da máquina. - INICIAR. - PARAR. -
Imagem da câmera. - Produto/classe atual. - Contador total. - Contadores
por classe. - Quantidade rejeitada. - Indicadores dos sensores. -
Indicadores das válvulas. - Acesso a configurações.

Tela de configurações: - Câmera. - ROI. - Cores/classes. -
Formatos/classes. - Velocidade da esteira. - Distâncias. - Tempos das
válvulas. - GPIOs. - Teste manual de entradas e saídas. - Calibração. -
Diagnóstico.

12. Modo de produção

No produto final: - Linux inicia. - Login automático, se apropriado. -
Serviços necessários iniciam. - Aplicativo do separador inicia
automaticamente. - Aplicativo abre em tela cheia. - Operador não precisa
acessar Cinnamon. - Em caso de falha do aplicativo, registrar logs para
diagnóstico.

O Cinnamon poderá continuar disponível para manutenção técnica.

13. Estrutura recomendada do projeto

separador_tampas/
|
+-- AGENTS.md
+-- PROJETO_SEPARADOR_TAMPAS.md
+-- README.md
+-- requirements.txt
+-- main.py
|
+-- app/
|   +-- __init__.py
|   +-- controller.py
|
+-- camera/
|   +-- __init__.py
|   +-- capture.py
|   +-- calibration.py
|
+-- vision/
|   +-- __init__.py
|   +-- detector.py
|   +-- color_classifier.py
|   +-- shape_classifier.py
|   +-- tracker.py
|
+-- hardware/
|   +-- __init__.py
|   +-- gpio.py
|   +-- sensors.py
|   +-- valves.py
|
+-- scheduler/
|   +-- __init__.py
|   +-- ejector.py
|
+-- ui/
|   +-- __init__.py
|   +-- main_window.py
|   +-- settings_window.py
|
+-- config/
|   +-- machine.yaml
|
+-- logs/
|
+-- tests/

A estrutura pode evoluir, mas evitar colocar todo o sistema em um único
arquivo Python.

14. Configuração da máquina

Parâmetros de hardware e produção não devem ficar espalhados pelo
código.

Centralizar em arquivo de configuração, por exemplo
config/machine.yaml.

Exemplo conceitual:

camera:
  device: 0
  width: 1280
  height: 720

conveyor:
  speed_mm_s: 300
  gpio: 19

outputs:
  red:
    gpio: 20
    delay_ms: 1500
    distance_mm: 500
    pulse_ms: 80

Os números acima usam a convenção wPi do wiringOP. A correspondência física
validada e os requisitos elétricos estão registrados nas decisões da seção 22.

15. Segurança de software

Ao iniciar o programa: - Todas as válvulas devem começar DESLIGADAS. -
Validar configuração antes de habilitar produção. - Se a câmera falhar,
entrar em estado seguro. - Se o módulo de GPIO falhar, não iniciar
produção. - Ao fechar o programa, desligar todas as saídas. - Tratar
exceções sem deixar válvulas permanentemente energizadas. - Registrar
falhas importantes.

Adicionar um modo SIMULAÇÃO para desenvolvimento sem hardware conectado.

16. Logs e diagnóstico

Registrar: - Inicialização. - Câmera detectada. - Sensores. - Eventos de
classificação. - Disparos das válvulas. - Erros. - FPS. - Tempo de
processamento. - Tampas rejeitadas.

Evitar gravar cada frame em disco durante produção normal.

17. Desempenho

Medir: - FPS real. - Latência média de processamento. - Latência
máxima. - Uso de CPU. - Uso de RAM. - Temperatura do Orange Pi. - Taxa
de tampas por minuto. - Erros de classificação. - Erros de expulsão.

O sistema deve priorizar previsibilidade e estabilidade em vez de
efeitos gráficos.

18. Desenvolvimento em etapas

Etapa 1

Validar sistema operacional, display e câmera.

Etapa 2

Criar captura de câmera estável.

Etapa 3

Detectar uma tampa sobre fundo controlado.

Etapa 4

Classificar cores.

Etapa 5

Classificar formatos.

Etapa 6

Adicionar rastreamento.

Etapa 7

Validar GPIO com LED/carga de teste segura.

Etapa 8

Adicionar sensores.

Etapa 9

Adicionar driver e válvula.

Etapa 10

Sincronizar detecção e jato de ar.

Etapa 11

Criar interface touchscreen.

Etapa 12

Adicionar inicialização automática e modo de produção.

Etapa 13

Testes de longa duração e otimização.

19. Regras para o Codex

Ao trabalhar neste projeto:

Leia este arquivo antes de alterações arquiteturais.

Não invente GPIOs do Orange Pi. Verifique a pinagem antes de definir
números reais.

Não acione válvulas diretamente por GPIO.

Preserve um modo de simulação.

Separe visão, hardware, interface e lógica.

Evite funções bloqueantes no caminho crítico.

Não introduza YOLO/IA pesada sem justificar a necessidade.

Crie código legível e modular.

Documente dependências novas.

Atualize este documento quando uma decisão importante de arquitetura
for confirmada.

Antes de alterar código funcional, avalie impacto nos módulos
dependentes.

Prefira configurações externas a números mágicos no código.

Mantenha o sistema capaz de operar sem internet.

Trate o equipamento como sistema industrial: comportamento seguro em
falhas é prioridade.

20. Primeira tarefa sugerida ao Codex

Ao iniciar uma nova sessão no VS Code, usar:

Leia PROJETO_SEPARADOR_TAMPAS.md por completo e trate-o como a
especificação principal do projeto. Analise a pasta atual. Primeiro
proponha a estrutura inicial do software para Orange Pi 4 Pro usando
Python e OpenCV, mantendo visão, GPIO, interface e temporização
desacoplados. Não defina GPIOs reais ainda. Implemente inicialmente um
modo de simulação e um módulo simples para detectar a câmera
disponível. Explique quais arquivos serão criados antes de realizar
alterações grandes.

21. Estado atual

Neste momento: - Orange Pi 4 Pro disponível. - 4 GB de RAM. -
Armbian/Debian 13 Trixie instalado. - Cinnamon instalado para
desenvolvimento/manutenção. - Tela de 7" conectada por controladora
universal. - Ajustes de resolução/overscan ainda em andamento. - VS Code
está sendo preparado no Orange Pi. - O desenvolvimento do software de
visão ainda deve começar pela validação da câmera.

22. Decisões de implementação registradas

2026-09-22:

- Criada a estrutura modular inicial do software em Python, separando
  aplicação, câmera, visão, hardware, scheduler, interface, configuração
  e testes.
- O modo de simulação foi definido como padrão em config/machine.yaml
  para permitir desenvolvimento sem hardware conectado.
- Na primeira etapa, os GPIOs reais permaneceram indefinidos até a consulta da
  pinagem oficial; a seleção confirmada está registrada abaixo.
- Na primeira etapa, o backend real de GPIO permaneceu bloqueado para evitar
  acionamento acidental antes da confirmação da pinagem.
- Foi criado um módulo simples de detecção de câmera com OpenCV, sem
  tornar a câmera física obrigatória no modo de simulação.
- A temporização inicial de expulsão usa fila de eventos e tick()
  não bloqueante, evitando sleep() longo para controlar válvulas.
- A primeira interface touchscreen foi implementada como aplicação web local,
  otimizada para a resolução de 800 x 480 e acessível sem internet. Ela mantém
  o controle da máquina no backend Python e usa o navegador apenas para a
  apresentação e a captura assistida de imagens.
- O cadastro de classes de tampas e suas amostras foi separado da lógica de
  visão. Os metadados são persistidos em data/cap_catalog.json e as imagens em
  data/cap_images/, permitindo treinamento ou calibração posterior sem definir
  antecipadamente um modelo de inteligência artificial.
- Foi adicionada uma interface desktop em Flet para desenvolvimento e testes
  com a câmera local. A interface web permanece disponível como alternativa.
  Ambas usam o mesmo catálogo de classes e imagens.
- O primeiro reconhecimento por imagens cadastradas usa características locais
  SIFT e validação geométrica por homografia. Resultados ambíguos ou com poucos
  pontos confirmados são rejeitados, e os limiares ficam centralizados em
  config/machine.yaml. Essa abordagem mantém a fase inicial sem modelo pesado
  de inteligência artificial.
- A operação exige calibração explícita do fundo vazio. A diferença entre o
  fundo calibrado e o quadro atual determina a presença de um objeto e limita
  a classificação à região alterada, evitando classificar o cenário sem tampa.
- As amostras podem ser excluídas individualmente pela interface Flet; a remoção
  atualiza o catálogo, apaga o arquivo correspondente e recarrega o
  classificador sem reiniciar o aplicativo.
- Os nomes visíveis das classes podem ser alterados sem mudar seus
  identificadores internos ou diretórios de imagens. A operação mantém
  contadores de peças por classe reconhecida durante a sessão.
- O perfil rápido de reconhecimento reduz os quadros para largura máxima de
  640 pixels, limita o SIFT a 900 características e agenda análises a cada
  75 ms. A latência efetiva é exibida na operação e todos esses parâmetros
  permanecem configuráveis em config/machine.yaml.
- A pinagem de controle foi conferida no manual oficial do Orange Pi 4 Pro e
  usa a numeração wPi do wiringOP: wPi 19 (pino físico 29, PD0) para o comando
  da esteira e wPi 20 (pino físico 31, PD1) para a primeira saída de expulsão.
  O pino físico 30 é GND de referência. O pino físico 1 não é usado por ser
  alimentação de 3,3 V, e não um GPIO.
- O backend real usa wiringOP-Python, mas o modo de simulação continua ativo
  por padrão. Motor, contator e válvulas nunca devem ser ligados diretamente
  aos GPIOs; a interface elétrica deve usar acionamento isolado e proteção
  adequada para cargas indutivas.
- Cada saída de expulsão possui GPIO wPi, polaridade, atraso após o
  reconhecimento e duração do pulso. O scheduler executa esses eventos sem
  bloquear a captura da câmera. A tela Ajustes permite editar, adicionar e
  remover saídas, persiste as mudanças em config/machine.yaml e bloqueia
  alterações enquanto a máquina está em operação.
- A interface Flet adota uma estrutura de console industrial para apresentação
  comercial: navegação lateral por Produção, Qualidade e Engenharia, contexto
  da área ativa, estados reais de máquina/câmera/catálogo e telemetria fixa no
  rodapé. A linguagem visual usa superfícies neutras, controles compactos e
  cores reservadas para estado e segurança, sem depender de serviços online.
- A área de Engenharia permite editar e persistir o nome da máquina, câmera
  USB, resolução, FPS, velocidade da esteira e parâmetros principais de
  reconhecimento. A busca de câmeras ocorre fora do caminho crítico. Uma troca
  de câmera só é aceita após receber um quadro; em caso de falha, o dispositivo
  anterior é restaurado. Alterações de câmera ou presença invalidam a
  calibração do fundo.
