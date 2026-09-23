# Instalacao no Orange Pi 4 Pro

Procedimento para Armbian com Debian 13 Trixie, kernel do fabricante e sessao
Cinnamon em Xorg/LightDM.

## 1. Baixar e instalar

Abra um terminal no Orange Pi:

```bash
cd ~
git clone https://github.com/alex201159/classificadora_img.git
cd classificadora_img
chmod +x scripts/*.sh
./scripts/install_orangepi.sh
```

O instalador usa `python3-opencv`, NumPy e PyYAML do Debian. Isso evita compilar
OpenCV na placa. O Flet e instalado no ambiente virtual `.venv`.

Ao terminar, encerre a sessao do Cinnamon e entre novamente. Isso aplica a
permissao do grupo `video` para acessar cameras USB.

## 2. Validar a camera

Conecte a camera diretamente a uma porta USB e execute:

```bash
cd ~/classificadora_img
./scripts/check_orangepi.sh
```

O diagnostico deve listar pelo menos um dispositivo em `Cameras V4L2` e em
`Deteccao pelo aplicativo`. Para inspecionar formatos e resolucoes aceitos:

```bash
v4l2-ctl --list-formats-ext --device=/dev/video0
```

Se a camera nao aparecer, confira `ls -l /dev/video*`, troque a porta ou cabo
USB e confirme que o usuario pertence ao grupo `video` com `id -nG`.

## 3. Abrir a interface

Dentro da sessao grafica Cinnamon:

```bash
cd ~/classificadora_img
./scripts/run_orangepi.sh
```

O lancador fixa o backend X11, apropriado para a sessao Xorg atual. A primeira
execucao do Flet pode baixar o cliente desktop e demorar um pouco mais.

Caso o cliente desktop nao abra no Debian 13, use temporariamente a interface
web para separar um problema do Flet de um problema da camera:

```bash
.venv/bin/python main.py --ui
```

## 4. Iniciar junto com o Cinnamon

Depois de validar camera e interface manualmente:

```bash
./scripts/install_autostart.sh
```

O programa sera iniciado cinco segundos depois do login grafico. Isso e mais
adequado para uma aplicacao desktop do que um servico de sistema, pois a janela
precisa da sessao Xorg do usuario.

## 5. Validar o GPIO sem carga industrial

Mantenha esta opcao em `config/machine.yaml`:

```yaml
machine:
  simulation: true
```

Primeiro execute `gpio readall`. A imagem oficial do Orange Pi deve identificar
corretamente a placa e mostrar a numeracao wPi. Se o comando `gpio` nao existir,
instale o wiringOP da ramificacao `next`, conforme o manual oficial da placa:

```bash
cd ~
sudo apt install -y build-essential git
git clone --branch next https://github.com/orangepi-xunlong/wiringOP.git
cd wiringOP
./build clean
./build
gpio readall
```

O software usa:

| Funcao | Numero wPi | Pino fisico | SoC |
| --- | ---: | ---: | --- |
| Esteira | 19 | 29 | PD0 |
| Expulsor 1 | 20 | 31 | PD1 |
| Referencia do circuito | - | 30 | GND |

O backend usa primeiro o modulo `wiringpi`, quando disponivel, e tambem aceita a
`libwiringPi.so` instalada pelo wiringOP oficial. O segundo caminho evita
depender do wiringOP-Python antigo. Execute novamente `check_orangepi.sh` e
confirme a mensagem `Backend Python do wiringOP inicializado`. Nao execute toda
a interface como root apenas para contornar permissao de GPIO.

Para acesso sem root, o kernel deve fornecer `/dev/gpiomem` com permissao para
o usuario, normalmente pelo grupo `gpio`. Confira com `ls -l /dev/gpiomem` e
`id -nG`; depois de adicionar um grupo e necessario sair e entrar novamente na
sessao. Se o dispositivo nao existir ou o diagnostico falhar, mantenha a
simulacao ativa ate preparar um servico de GPIO isolado.

Teste os pinos primeiro com LED e resistor ou entrada isolada de um modulo de
interface. Nunca conecte motor, valvula, bobina ou contator diretamente ao GPIO.
Somente depois de validar polaridade, estado seguro e desligamento de emergencia
altere `machine.simulation` para `false`.

## 6. Atualizar o programa

Com a maquina parada e o programa fechado:

```bash
cd ~/classificadora_img
git pull --ff-only
.venv/bin/python -m pytest -q
./scripts/run_orangepi.sh
```

Antes de atualizar, mantenha uma copia de `config/machine.yaml`,
`data/cap_catalog.json` e `data/cap_images/`, pois esses arquivos representam a
configuracao e as amostras cadastradas na maquina.
