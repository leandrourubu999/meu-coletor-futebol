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
EMAIL = os.getenv("SITE_EMAIL", "erro_sem_email")
SENHA = os.getenv("SITE_SENHA", "erro_sem_senha")
WEBHOOK_N8N = os.getenv("N8N_WEBHOOK", "")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=chrome_options)

def rodar_coleta():
    logging.info("--- Iniciando Diagnóstico ---")
    driver = get_driver()
    
    try:
        # 1. Login
        driver.get(URL_LOGIN)
        time.sleep(5)
        
        logging.info(f"URL antes do login: {driver.current_url}")
        
        driver.find_element(By.NAME, "email").send_keys(EMAIL)
        driver.find_element(By.NAME, "password").send_keys(SENHA)
        
        btn_login = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].click();", btn_login)
        
        time.sleep(8) # Espera maior
        logging.info(f"URL após login: {driver.current_url}")

        if "login" in driver.current_url:
            logging.error("❌ O robô ainda está na página de login! Senha incorreta ou Captcha.")
            return

        # 2. Ir para Matches
        driver.get(URL_MATCHES)
        time.sleep(8)
        
        # 3. Expandir Ligas
        botoes = driver.find_elements(By.CLASS_NAME, "titulo-liga") # Tenta clicar na barra inteira
        logging.info(f"Encontradas {len(botoes)} ligas. Tentando clicar...")
        
        for btn in botoes:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.5)
            except: pass
        
        logging.info("Aguardando carregamento dos jogos (10s)...")
        time.sleep(10)

        # 4. Investigar Links (AQUI ESTÁ A CHAVE)
        # Vamos pegar TODOS os links da página para ver como eles são
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        todos_links = soup.find_all('a')
        
        match_links = []
        exemplos_encontrados = []

        for link in todos_links:
            href = link.get('href')
            if href:
                # Guarda alguns exemplos para mostrar no log
                if len(exemplos_encontrados) < 5 and len(href) > 5:
                    exemplos_encontrados.append(href)
                
                # Tenta filtrar o que queremos
                if "/match/" in href or "/jogo/" in href:
                    match_links.append(href)

        logging.info(f"Total de links brutos na página: {len(todos_links)}")
        logging.info(f"Exemplos de links encontrados: {exemplos_encontrados}")
        logging.info(f"Jogos filtrados: {len(match_links)}")

        # 5. Se achou jogos, processa (Código antigo)
        if match_links:
            match_links = list(set(match_links))
            dados_totais = []
            # Pega só o primeiro para teste rápido
            logging.info(f"Testando extração no primeiro jogo: {match_links[0]}")
            
            driver.get(match_links[0])
            time.sleep(5)
            soup_jogo = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Tenta pegar mandante só para provar que funcionou
            try:
                times = soup_jogo.find_all(class_="nome-time")
                m = times[0].get_text(strip=True)
                v = times[1].get_text(strip=True)
                logging.info(f"✅ SUCESSO! Jogo lido: {m} x {v}")
                
                # Se chegou aqui, envia teste pro n8n
                if WEBHOOK_N8N:
                    requests.post(WEBHOOK_N8N, json={"mensagem": "Robô conectou!", "jogo": f"{m}x{v}"})
                    logging.info("Webhook disparado.")
            except:
                logging.error("Entrou no jogo mas não achou os nomes dos times.")

    except Exception as e:
        logging.error(f"Erro fatal: {e}")
    finally:
        driver.quit()

# Loop lento para não floodar o log
if __name__ == "__main__":
    while True:
        rodar_coleta()
        logging.info("Dormindo 1 hora...")
        time.sleep(3600)
