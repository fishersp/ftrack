#!/bin/bash

# Путь к n8n
N8N_PATH="/path/to/n8n"

# Имя workflow
WORKFLOW_NAME="fintrack-save-file"

# Запуск workflow через Cron
$N8N_PATH run workflow "$WORKFLOW_NAME"