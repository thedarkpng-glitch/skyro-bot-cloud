# Bot Host Panel

Painel web local para hospedar bots Python e Node.js em uma VM Windows.

## Stack

- Backend: Python + Flask
- Banco: SQLite
- Frontend: HTML/CSS/JavaScript
- Editor: Monaco Editor via CDN
- Processos: subprocess
- Monitoramento: psutil
- Upload: ZIP
- Python: detecta `py -0p` e `python`
- Node.js: detecta `node`
- Logs de webhook: salvos em SQLite

## Instalação

Abra PowerShell como administrador:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

Depois:

```powershell
python app.py
```

Abra:

http://127.0.0.1:5000

## Senhas

Na primeira inicialização, o painel mostra uma senha administrativa temporária no terminal.

Altere depois em `data/config.json`.

Não publique a porta 5000 diretamente na internet sem colocar autenticação/reverse proxy.

## Bot

Ao criar um bot:

- escolha Python ou Node.js;
- envie ZIP ou crie arquivos no editor;
- configure o arquivo de entrada;
- configure variáveis de ambiente;
- inicie/reinicie/parar o processo.

O console permite comandos comuns como:

```text
pip install discord.py
npm install
python --version
node --version
```

Comandos `shutdown` e `restart` são tratados como ações do bot.

## Observação

Este MVP executa comandos no diretório do bot. Por isso ele deve ser usado apenas por pessoas autorizadas. Para colocar na internet, adicione autenticação de usuários, HTTPS, limites de CPU/RAM e isolamento por container/VM.


# GitHub Actions + RDP

Coloque o projeto no repositório GitHub e o arquivo
`.github/workflows/windows-panel.yml` será o workflow.

## Secrets obrigatórios

No GitHub:
Settings -> Secrets and variables -> Actions -> New repository secret

Crie:

- `TAILSCALE_AUTH_KEY`: Auth Key do Tailscale
- `RDP_PASSWORD`: senha que você escolheu para o usuário `Skyro`

Nunca coloque essas credenciais diretamente no YAML.

## Execução

GitHub -> Actions -> Skyro Bot Cloud - Windows -> Run workflow.

O workflow instala/verifica Python, Node.js e VS Code, configura Tailscale/RDP,
cria `Skyro` sem colocá-lo em Administrators, inicia o painel e mantém o job vivo.

## Importante sobre GitHub

Este workflow não contorna limites de uso, cobrança, falha de pagamento,
spending limit ou indisponibilidade de runners. Se o GitHub bloquear o job
por Billing & plans, primeiro resolva a situação da conta ou use outro
provedor de runner.

## Acesso ao painel

Por segurança, o Flask escuta em `127.0.0.1:5000`. Para acessar o painel de
dentro da VM via RDP, abra:

http://127.0.0.1:5000

Não exponha essa porta publicamente nesta versão.
