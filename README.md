# Separador automatico de tampas

Base inicial em Python para o separador automatico descrito em
`PROJETO_SEPARADOR_TAMPAS.md`.

## Estado atual

- Modo de simulacao habilitado por padrao.
- Estrutura modular para camera, visao, hardware, scheduler e UI.
- Deteccao simples de cameras disponiveis via OpenCV, quando instalado.
- Interface local para operacao e cadastro de imagens das tampas.
- Temporizacao e multiplas saidas de expulsao configuraveis pela interface.
- Backend GPIO wiringOP implementado, com simulacao ativa por padrao.
- Pipeline de producao com ROI unica, deteccao, IDs persistentes, votacao por
  tampa e decisao unica de contagem/expulsao.
- Scheduler nao bloqueante que preserva pulsos sobrepostos na mesma valvula.

## Uso

Para instalar no Orange Pi 4 Pro com Armbian/Debian 13 e Cinnamon, siga o guia
[docs/INSTALACAO_ORANGE_PI.md](docs/INSTALACAO_ORANGE_PI.md). O repositorio
inclui scripts para instalar dependencias, diagnosticar camera, abrir a
interface em Xorg e habilitar a inicializacao automatica apos o login.

Instale as dependencias:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Executar uma inicializacao segura em simulacao:

```bash
python main.py --once
```

Abrir a interface para testes:

```bash
python main.py --ui
```

A interface abre em `http://127.0.0.1:8080`. Na aba **Cadastro**, crie o
tipo de tampa, selecione-o e use a camera ou um arquivo JPEG/PNG para adicionar
amostras. O catalogo fica em `data/cap_catalog.json` e as imagens em
`data/cap_images/`.

Abrir a interface desktop Flet com camera e reconhecimento em tempo real:

```bash
python main.py --flet
```

No macOS, autorize o Python a acessar a camera quando o sistema solicitar. Para
melhor reconhecimento, centralize o objeto no quadro verde e cadastre pelo
menos tres imagens em distancias e inclinacoes ligeiramente diferentes.
Antes de iniciar a operacao, retire o objeto da imagem e use **Calibrar fundo**.
As amostras podem ser removidas pelo botao de lixeira na tela de cadastro.
O nome da classe selecionada pode ser alterado pelo campo **Novo nome da
classe**. A tela de operacao mostra a contagem total e a quantidade reconhecida
de cada tipo durante a sessao atual.

O perfil inicial de reconhecimento rapido processa os recortes das tampas com
largura maxima de 640 px e inicia uma nova analise a cada 75 ms. Cada tampa
recebe um ID e precisa acumular tres votos por padrao antes da decisao. ROI,
distancia de tracking, tolerancia a frames perdidos e margem do crop ficam na
secao `recognition` de `config/machine.yaml`. A tela mostra IDs, FPS e latencia.

Na aba **Ajustes**, cada expulsor pode receber um GPIO wPi, o atraso entre o
reconhecimento e o disparo e a duracao do pulso. A mesma tela permite adicionar
ou excluir saidas. As alteracoes exigem que a maquina esteja parada e sao
salvas em `config/machine.yaml`.

A mesma aba permite alterar o nome da maquina, procurar e selecionar cameras
USB, escolher resolucao e FPS, ajustar a velocidade da esteira e calibrar os
principais parametros de reconhecimento. A troca de camera e aplicada sem
reiniciar o programa; se o novo dispositivo nao fornecer imagem, a camera
anterior e restaurada. Mudancas de camera ou deteccao de presenca exigem uma
nova calibracao do fundo.

Listar cameras detectaveis:

```bash
python main.py --detect-cameras
```

Usar outro arquivo de configuracao:

```bash
python main.py --config config/machine.yaml --once
```

## Testes

```bash
pytest
```

## Observacoes de seguranca

O sistema inicia com as valvulas e a esteira desligadas. A configuracao usa
numeracao wiringOP: wPi 19 no pino fisico 29 (PD0) para a esteira e wPi 20 no
pino fisico 31 (PD1) para o primeiro expulsor. O pino fisico 30 pode ser usado
como referencia GND do circuito de interface. O modo real aceita o modulo
`wiringOP-Python` ou a `libwiringPi.so` do wiringOP no Orange Pi.

Nunca ligue motor, contator ou valvula diretamente ao GPIO. Use modulo de rele
ou driver MOSFET/optoacoplado dimensionado para a carga e protecao de retorno
na bobina. Mantenha `machine.simulation: true` ate validar toda a interface
eletrica no equipamento.
