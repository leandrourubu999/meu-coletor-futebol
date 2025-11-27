import time
import json
import os
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES ---
URL_LOGIN = "https://clube.theoborges.com/login"
URL_MATCHES = "https://clube.theoborges.com/matches"
EMAIL = os.getenv("SITE_EMAIL", "seu_email_aqui") # Pega das variáveis do Easypanel
SENHA = os.getenv("SITE_SENHA", "sua_senha_aqui")
WEBHOOK_N8N = os.getenv("N8N_WEBHOOK", "COLOQUE_SEU_WEBHOOK_DO_N8N_AQUI")

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=chrome_options)

def rodar_coleta():
    print("Iniciando robô...")
    driver = get_driver()
    
    try:
        # 1. Login
        driver.get(URL_LOGIN)
        time.sleep(2)
        driver.find_element(By.NAME, "email").send_keys(EMAIL)
        driver.find_element(By.NAME, "password").send_keys(SENHA)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(5)
        print("Login OK.")

        # 2. Ir para Matches e Expandir
        driver.get(URL_MATCHES)
        time.sleep(5)
        
        botoes = driver.find_elements(By.CLASS_NAME, "toggle-partidas")
        if not botoes:
            botoes = driver.find_elements(By.CLASS_NAME, "titulo-liga")
            
        print(f"Expandindo {len(botoes)} ligas...")
        for btn in botoes:
            try:
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.5)
            except: pass
        
        time.sleep(5)

        # 3. Pegar Links
        links = []
        elementos = driver.find_elements(By.CSS_SELECTOR, "a[href*='/match/']")
        for el in elementos:
            links.append(el.get_attribute("href"))
        links = list(set(links))
        print(f"Jogos encontrados: {len(links)}")

        # 4. Entrar em cada jogo
        dados_totais = []
        for url in links:
            print(f"Lendo: {url}")
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
            for i, tab in enumerate(tabelas):
                lado = nomes_lados[i] if i < 2 else f"extra_{i}"
                for row in tab.find_all("tr"):
                    cols = row.find_all("td")
                    if len(cols) == 2:
                        chave = cols[0].get_text(strip=True).replace(" ", "_").lower()
                        val = cols[1].get_text(strip=True)
                        jogo[f"{lado}_{chave}"] = val
            
            dados_totais.append(jogo)

        # 5. Enviar para o n8n
        print("Enviando dados para o n8n...")
        requests.post(WEBHOOK_N8N, json=dados_totais)
        print("Finalizado com sucesso!")

    except Exception as e:
        print(f"Erro fatal: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    rodar_coleta()
