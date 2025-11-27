import time
import json
import os
import requests
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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

def garantir_ligas_expandidas(driver):
    """Função auxiliar para garantir que os jogos estão visíveis"""
    try:
        botoes = driver.find_elements(By.CLASS_NAME, "titulo-liga")
        for btn in botoes:
            # Tenta clicar apenas se parecer fechado (lógica simplificada: clica sempre)
            try:
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.2)
            except: pass
    except: pass
    time.sleep(2)

def rodar_coleta():
    logging.info("--- Iniciando Coleta Por Clique ---")
    driver = get_driver()
    
    try:
        # 1. Login
        logging.info("Fazendo Login...")
        driver.get(URL_LOGIN)
        time.sleep(5)
        
        driver.find_element(By.NAME, "email").send_keys(EMAIL)
        driver.find_element(By.NAME, "password").send_keys(SENHA)
        btn_login = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].click();", btn_login)
        
        time.sleep(8)
        
        if "login" in driver.current_url:
            logging.error("❌ Falha no login (ainda na URL de login).")
            return

        # 2. Ir para Matches
        logging.info("Indo para Matches...")
        driver.get(URL_MATCHES)
        time.sleep(8)
        
        # 3. Expandir Ligas
        garantir_ligas_expandidas(driver)
        
        # 4. Contar Jogos (Classe .jogo-detalhes que vimos nos seus prints antigos)
        elementos_jogos = driver.find_elements(By.CLASS_NAME, "jogo-detalhes")
        total_jogos = len(elementos_jogos)
        logging.info(f"✅ Encontrei {total_jogos} caixas de jogos na tela!")

        if total_jogos == 0:
            logging.warning("Nenhum jogo encontrado. Verifique se há jogos hoje.")
            return

        # 5. Loop: Clicar, Raspar, Voltar
        # Limitado a 5 jogos para teste rápido (remova [:5] para pegar todos)
        for i in range(total_jogos):
            logging.info(f"--- Processando jogo {i+1} de {total_jogos} ---")
            
            try:
                # Re-encontra os elementos (pois a página mudou quando voltamos)
                garantir_ligas_expandidas(driver)
                jogos_atualizados = driver.find_elements(By.CLASS_NAME, "jogo-detalhes")
                
                if i >= len(jogos_atualizados):
                    break
                
                jogo_alvo = jogos_atualizados[i]
                
                # Scroll e Clique
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", jogo_alvo)
                time.sleep(1)
                
                # Tenta clicar no elemento ou num link dentro dele
                try:
                    driver.execute_script("arguments[0].click();", jogo_alvo)
                except:
                    logging.warning("Clique falhou, tentando link interno...")
                    # Fallback
                    pass
                
                time.sleep(5) # Espera carregar detalhes
                
                # --- RASPAGEM DA PÁGINA INTERNA ---
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                dados_jogo = {"url": driver.current_url}
                
                # Nomes dos Times
                try:
                    nomes = soup.find_all(class_="nome-time")
                    if len(nomes) >= 2:
                        dados_jogo["mandante"] = nomes[0].get_text(strip=True)
                        dados_jogo["visitante"] = nomes[1].get_text(strip=True)
                        logging.info(f"Jogo: {dados_jogo['mandante']} x {dados_jogo['visitante']}")
                except:
                    logging.warning("Não achei nome dos times.")

                # Pega TODAS as tabelas de estatísticas
                tabelas = soup.find_all("table", class_="tabela-estatisticas")
                lados = ["casa", "fora"]
                for k, tab in enumerate(tabelas):
                    lado = lados[k] if k < 2 else f"tab_{k}"
                    for row in tab.find_all("tr"):
                        cols = row.find_all("td")
                        if len(cols) == 2:
                            chave = cols[0].get_text(strip=True).lower().replace(" ", "_")
                            valor = cols[1].get_text(strip=True)
                            dados_jogo[f"{lado}_{chave}"] = valor

                # Envia para n8n um por um
                if WEBHOOK_N8N:
                    requests.post(WEBHOOK_N8N, json=dados_jogo)
                    logging.info("Enviado para n8n.")

                # Voltar para lista
                driver.back()
                time.sleep(3)
                
            except Exception as e:
                logging.error(f"Erro no jogo {i}: {e}")
                driver.get(URL_MATCHES) # Tenta recuperar voltando pra home
                time.sleep(5)

    except Exception as e:
        logging.error(f"Erro fatal: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    while True:
        rodar_coleta()
        logging.info("Dormindo 24 horas...")
        time.sleep(86400)
