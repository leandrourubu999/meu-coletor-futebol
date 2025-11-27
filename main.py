import time
import json
import os
import requests
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES ---
URL_LOGIN = "https://clube.theoborges.com/login"
URL_MATCHES = "https://clube.theoborges.com/matches"
# Pega as variáveis do Easypanel ou usa valores de teste se não encontrar
EMAIL = os.getenv("SITE_EMAIL", "seu_email")
SENHA = os.getenv("SITE_SENHA", "sua_senha")
WEBHOOK_N8N = os.getenv("N8N_WEBHOOK", "")

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080") # Define tela grande para evitar menus mobile
    return webdriver.Chrome(options=chrome_options)

def rodar_coleta():
    logging.info("--- Iniciando nova execução ---")
    driver = get_driver()
    
    try:
        # 1. Login
        logging.info("Acessando login...")
        driver.get(URL_LOGIN)
        time.sleep(5) # Espera carregar bem
        
        # Preenche campos
        driver.find_element(By.NAME, "email").send_keys(EMAIL)
        driver.find_element(By.NAME, "password").send_keys(SENHA)
        
        # --- O TRUQUE DO CLIQUE FORÇADO ---
        # Em vez de clicar normal, usamos JS para ignorar banners na frente
        btn_login = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].click();", btn_login)
        
        time.sleep(5)
        logging.info("Login enviado (espero).")

        # 2. Ir para Matches
        logging.info("Indo para página de jogos...")
        driver.get(URL_MATCHES)
        time.sleep(5)
        
        # Tenta expandir ligas
        try:
            botoes = driver.find_elements(By.CLASS_NAME, "toggle-partidas")
            if not botoes:
                botoes = driver.find_elements(By.CLASS_NAME, "titulo-liga")
            
            logging.info(f"Tentando expandir {len(botoes)} ligas...")
            for btn in botoes:
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.2)
        except:
            pass
        
        time.sleep(5) # Espera carregar os jogos

        # 3. Pegar Links
        links = []
        elementos = driver.find_elements(By.CSS_SELECTOR, "a[href*='/match/']")
        for el in elementos:
            links.append(el.get_attribute("href"))
        # Remove duplicatas
        links = list(set(links))
        logging.info(f"Jogos encontrados para analisar: {len(links)}")

        if len(links) == 0:
            logging.warning("Nenhum link encontrado! Talvez o login tenha falhado ou não há jogos.")
            return

        # 4. Entrar em cada jogo
        dados_totais = []
        for i, url in enumerate(links):
            logging.info(f"Lendo jogo {i+1}/{len(links)}: {url}")
            try:
                driver.get(url)
                time.sleep(3)
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                jogo = {"url": url}
                
                # Times
                times = soup.find_all(class_="nome-time")
                if len(times) >= 2:
                    jogo["mandante"] = times[0].get_text(strip=True)
                    jogo["visitante"] = times[1].get_text(strip=True)

                # Estatísticas
                tabelas = soup.find_all("table", class_="tabela-estatisticas")
                nomes_lados = ["casa", "fora"]
                for k, tab in enumerate(tabelas):
                    lado = nomes_lados[k] if k < 2 else f"extra_{k}"
                    for row in tab.find_all("tr"):
                        cols = row.find_all("td")
                        if len(cols) == 2:
                            chave = cols[0].get_text(strip=True).replace(" ", "_").lower()
                            val = cols[1].get_text(strip=True)
                            jogo[f"{lado}_{chave}"] = val
                
                dados_totais.append(jogo)
            except Exception as e:
                logging.error(f"Erro ao ler jogo {url}: {e}")

        # 5. Enviar para o n8n
        logging.info("Enviando dados para o n8n...")
        try:
            if WEBHOOK_N8N:
                requests.post(WEBHOOK_N8N, json=dados_totais)
                logging.info("Dados enviados com sucesso!")
            else:
                logging.warning("Sem Webhook configurado. Dados não enviados.")
        except Exception as e:
            logging.error(f"Erro ao enviar para n8n: {e}")

    except Exception as e:
        logging.error(f"Erro fatal na execução: {e}")
    finally:
        driver.quit()

# --- LOOP ETERNO ---
if __name__ == "__main__":
    logging.info(">>> ROBO INICIADO <<<")
    while True:
        rodar_coleta()
        
        # Espera 24 horas antes de rodar de novo (86400 segundos)
        # Se quiser testar rápido, mude para 300 (5 minutos)
        TEMPO_ESPERA = 86400 
        logging.info(f"Dormindo por {TEMPO_ESPERA} segundos...")
        time.sleep(TEMPO_ESPERA)
