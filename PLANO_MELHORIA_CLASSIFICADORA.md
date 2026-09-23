# Plano de melhoria da classificadora de tampas

## Objetivo

Evoluir o projeto sem reescrever sua arquitetura ou remover funcionalidades.
O fluxo de producao desta fase e:

```text
camera -> ROI -> deteccao -> rastreamento por ID -> classificacao
       -> decisao -> agendamento -> expulsor
```

O modo de simulacao deve permanecer funcional durante todo o desenvolvimento.

## Regras

- Ler `AGENTS.md` e `PROJETO_SEPARADOR_TAMPAS.md` antes de editar.
- Trabalhar em branch separada e executar testes entre as fases.
- Nao alterar GPIO fisico sem autorizacao.
- Preservar `SimulatedGPIO`, `OrangePiGPIO`, Flet, catalogo e configuracoes.
- Nao acionar solenoides diretamente por GPIO.
- Nao substituir SIFT/FLANN por YOLO nesta etapa.
- Nao usar `sleep()` no loop principal nem misturar UI com GPIO.
- Manter o sistema independente de internet durante a operacao.

## Rastreamento

Integrar efetivamente `vision/detector.py` e `vision/tracker.py`. Cada tampa deve
ter ID persistente e estado com centroide, bounding box, classe, confianca,
hits, frames perdidos, votos, flags de contagem/agendamento e ultimo instante
observado.

- Uma deteccao e um ID so podem participar de uma associacao por frame.
- `max_missed_frames` deve ser configuravel.
- Objetos ausentes temporariamente devem recuperar o ID.
- IDs removidos devem ficar disponiveis para finalizar seu estado.
- Ordem diferente das deteccoes nao deve trocar identidades.
- Cada ID pode ser contado e agendado no maximo uma vez.
- `scheduled` deve ser marcado antes da chamada ao scheduler.

## ROI e deteccao

A ROI oficial vem de `config/machine.yaml` e deve ser compartilhada por
presenca, detector, crops e anotacao. O fallback de 12% a 88% permanece apenas
quando nenhuma ROI explicita for fornecida ao detector de presenca.

Devem ser rejeitadas ROIs com origem negativa, dimensoes nao positivas ou que
estejam total ou parcialmente fora do frame. Detectores que processam recortes
devem retornar bounding boxes e centroides no sistema de coordenadas global.

O detector deve manter area minima configuravel, usar Otsu com polaridade
coerente com o fundo, morfologia moderada e evitar filtros que removam tampas
pequenas.

## Classificacao por ID

Classificar o crop de cada tampa com margem configuravel, preservando
`ReferenceImageClassifier`. Acumular votos por ID e consolidar por maioria,
usando confianca e inliers como desempate. Evidencia insuficiente permanece
como `NAO RECONHECIDO`.

Parametros centralizados:

```yaml
recognition:
  stable_hits: 3
  max_tracking_distance_px: 60
  max_missed_frames: 3
  crop_margin_px: 15
```

Nao criar limiares arbitrarios de cor ou formato nesta etapa. Manter interfaces
preparadas para um classificador hibrido futuro.

## Scheduler e seguranca

Preservar o scheduler nao bloqueante e o calculo por atraso configurado ou por
distancia/velocidade com compensacoes. Pulsos sobrepostos na mesma saida devem
manter a valvula ativa ate o fim de todos os pulsos aplicaveis.

Falhas criticas devem parar a esteira, limpar o scheduler, desligar valvulas e
ser registradas. Falha de camera durante producao deve entrar em estado seguro.

## Metricas

Adicionar, sem log por frame: FPS de captura/processamento, tempos de deteccao
e classificacao, latencia media/maxima, detectadas, reconhecidas, nao
reconhecidas, rejeitadas, expulsões agendadas e falhas.

## Cobertura minima

1. Persistencia e recuperacao de IDs.
2. Duas tampas nao compartilham ID.
3. Ordem das deteccoes nao altera identidade.
4. Remocao apos o limite de frames perdidos.
5. Contagem e agendamento unicos por tampa.
6. Politica de rejeicao para nao reconhecidas.
7. ROI global e validacao de ROI invalida.
8. Estado seguro em parada e falha critica.
9. Ordem do scheduler e pulsos sobrepostos.
10. Saidas simuladas desligadas no encerramento.
11. Configuracoes invalidas rejeitadas.
12. Pipeline funcional sem hardware fisico.

## Criterio de conclusao

Testes antigos e novos passam; IDs sao persistentes; multiplas tampas sao
rastreadas; classificacao, contagem e agendamento pertencem ao ID; ROI vem da
configuracao; pulsos proximos sao seguros; falhas deixam o hardware em estado
seguro; simulacao continua funcional; documentacao e configuracao estao
atualizadas; nenhum GPIO novo e assumido.

Depois da estabilidade em simulacao, a entrada do hardware deve ocorrer nesta
ordem: visao, logica, LED, driver/opto, estagio de potencia e pneumatica.

## Validacao fisica futura

1. Conectar a camera real.
2. Ajustar a ROI pela imagem real.
3. Coletar imagens reais das tampas.
4. Medir o desempenho do SIFT.
5. Avaliar classificador hibrido de cor, geometria e SIFT.
6. Testar GPIO com LED e resistor.
7. Validar o driver eletrico isolado.
8. Testar uma valvula.
9. Medir a velocidade real da esteira.
10. Calibrar a distancia entre camera e expulsor.
11. Testar multiplas tampas.
12. Executar teste prolongado.
