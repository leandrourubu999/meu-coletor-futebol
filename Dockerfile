FROM python:3.9-slim

# Instala Chrome e dependências do sistema
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Configura pasta de trabalho
WORKDIR /app

# Instala bibliotecas Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o script
COPY main.py .

# Comando para rodar
CMD ["python", "main.py"]
