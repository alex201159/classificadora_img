# Orientacoes do projeto

- `PROJETO_SEPARADOR_TAMPAS.md` e a especificacao principal deste projeto.
- Leia a especificacao antes de alterar arquitetura, temporizacao, GPIO, camera ou interface.
- Preserve o modo de simulacao para desenvolvimento sem hardware conectado.
- Nao defina GPIOs reais do Orange Pi sem validar a pinagem no equipamento.
- Nao acione valvulas diretamente por GPIO; mantenha a separacao entre logica, GPIO e potencia.
- Prefira configuracoes externas em `config/machine.yaml` a numeros magicos no codigo.
- O comportamento seguro em falhas tem prioridade sobre novas funcionalidades.
