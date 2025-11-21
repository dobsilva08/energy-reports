name: Gas — JKM LNG Diário

on:
  schedule:
    - cron: "11 9 * * *"   # 06:11 BRT
  workflow_dispatch:
    inputs:
      preview:
        type: boolean
        default: false
        description: "Enviar para TESTE (preview)"

concurrency:
  group: gas-jkm-lng-daily
  cancel-in-progress: false

jobs:
  run:
    runs-on: ubuntu-latest

    env:
      # ==== APIs ====
      FRED_API_KEY: ${{ secrets.FRED_API_KEY }}   # <- FALTAVA
      EIA_API_KEY: ${{ secrets.EIA_API_KEY }}

      # ==== Telegram ====
      TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
      # mapeia o mesmo chat para as duas variáveis, caso o script use uma ou outra
      TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID_ENERGY }}
      TELEGRAM_CHAT_ID_ENERGY: ${{ secrets.TELEGRAM_CHAT_ID_ENERGY }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Instalar dependências
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then
            pip install -r requirements.txt
          fi

      - name: Rodar jkm_lng_daily.py
        run: |
          mkdir -p pipelines/gas
          OUT_FILE="pipelines/gas/jkm_lng_daily.json"

          if [ "${{ github.event_name }}" = "workflow_dispatch" ] && [ "${{ github.event.inputs.preview }}" = "true" ]; then
            python scripts/gas/jkm_lng_daily.py --out "$OUT_FILE" --preview
          else
            python scripts/gas/jkm_lng_daily.py --out "$OUT_FILE"
          fi
