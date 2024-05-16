import requests
import os
import google.generativeai as genai
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
CLOUD_KEY = os.environ.get("CLOUD_KEY")
CX = os.environ.get("CX")

URL = "https://www.googleapis.com/customsearch/v1"

DATE_RESTRICTION = "m3"
START = [1,11]

NUMERO_DE_DOMINIOS = 5 # Numeros de dominios de busca para usar (quanto mais, melhor, porém mais demorado e com maior consumo de tokens)
MAX_REPETICAO = 2 # Numero máximos de repetições aceitas de links em mesmo domínio. Pouco adianta comparar 5 notícias de um mesmo portal

NUBER_OF_RESULTS = NUMERO_DE_DOMINIOS * MAX_REPETICAO * 2

DOMINIOS_DE_BUSCA = [
    "https://exame.com/",
    "https://www.cnnbrasil.com.br/",
    "https://www.cartacapital.com.br/",
    "https://www.poder360.com.br/",
    "https://www.bbc.com/",
    "https://g1.globo.com/",
    "https://www.poder360.com.br/", # Até aqui coloquei sites de notícias abertos
    "https://www.in.gov.br/",
    "https://www12.senado.leg.br/",
    "https://www.camara.leg.br/",
    "https://www.gov.br",
    "https://www.cnj.jus.br/", # Até aqui inclui sites oficiais mais importantes do governo federal.
    "https://agenciabrasil.ebc.com.br/",
    "https://noticias.uol.com.br/confere/",
    "https://checamos.afp.com/",
    "https://lupa.uol.com.br/",
    "https://www.boatos.org/",
    "https://projetocomprova.com.br/",
    "https://www.e-farsas.com/" # Até aqui incluí portais de verifcações de fatos profissionais, para caso a notícia já tenha sido verificada.
]

#Inicialização do modelo GEMINI
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.0-pro')

log=[]

def search(query, log=log, num_res = 20, key=CLOUD_KEY, cx=CX, url=URL, date_rest = DATE_RESTRICTION):
    
    NUMBER_OF_RESULTS = 10
    
    #define number of runs
    n = (num_res-1)//NUMBER_OF_RESULTS + 1
    START = [x*10 + 1 for x in range(n)]

    links = []
    for start in START:
        PARAMETERS = {
            "start": start, 
            'q': query, 
            'key': key, 
            'cx': cx, 
            'num': NUMBER_OF_RESULTS, 
            'dateRestrict': date_rest, 
            'filter': 1, 
            'safe': 'active'
            }
        response = requests.get(url, params=PARAMETERS)
        if response.status_code == 200:
            data = response.json()
            if 'items' in data.keys():
                for item in data['items']:
                    links.append(item['link'])
                log.append({'function':'query', 'status': "OK - start " + str(start) + " - " + str(len(links)) + " results", 'object': str(links)})
            else:
                log.append({'function':'query', 'status': "NOK - start " + str(start) + " - Warning: empty items", 'object': str(data)})
        else:
            log.append({'function':'query', 'status': f"Error: {response.status_code}"})

    return links, log

# Função busca de links relacionados ao critério de busca 'resultados'
def listar_links(results, dominios=DOMINIOS_DE_BUSCA, n=NUMERO_DE_DOMINIOS):
  """
  A Função executa busca no Google Search usando a variável 'resultados'
  Busca restrita aos domínios = lista de dominios
  n = numero de links a retornar, se 0 ele usa a quantidade de dominios listados
  Retorna lista de links
  """
  if n == 0:
    n = len(dominios)
  links = []
  for result in results:
    # Verificar contagem de dominio repetitivo para não ultrapassar limite estabelecido
    if verify_domains_max(result, links):
      links.append(result)
      n = n - 1
      if n == 0 :
        break
  return links

# verifica a contagens de dominios já utilizados para evitar repetições
def verify_domains_max(result, links):
  """
  retorna TRUE ou FALSE se a quantidade de dominios passou do limite
  """
  #identificar dominio
  the_domain = "new_domain"
  for domain in DOMINIOS_DE_BUSCA:
    if domain in result:
      the_domain = domain
      break
  # Contar quantas vezes dominio aparece em links
  c = 0
  for link in links:
    if the_domain in link:
      c = c + 1
  # Verifica ontagem
  if c >= MAX_REPETICAO:
    return False
  else:
    return True

# Usar Gemini para compilar textos
def compilar_noticias(links, noticias, log=log):
  """
  Le as notícias usando o Gemini e retorna JSON com titulo, conteudo e fonte
  """
  for url in links:
    log.append({'function':'compilar_noticias', 'status': 'Lendo Informação', 'object': url})
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    try:
      # Tente executar o comando
      # Nos testes vi que muitos sites não tem título definido desta forma...
      title = soup.title.string
      log.append({'function':'compilar_noticias', 'status': 'Notícia encontrada', 'object': title})
    except Exception as error:
      # Se ocorrer um erro, execute a ação alternativa
      log.append({'function':'compilar_noticias', 'status': str(error), 'object': url})
      title = "Noticia"
    text_soup = soup.getText()
    try:
      gen_response = model.generate_content(
          "Transcrever o artigo principa em meio à sopa de letras e codigos:" + text_soup,
          generation_config=genai.types.GenerationConfig(
            candidate_count=1,
            temperature=0) # Temperatura zero pois a rede não deve criar, apenas transcrever
          ).text
      noticias.append({"title": title, "news": gen_response, "source": url})
      log.append({'function':'compilar_noticias', 'status': 'OK', 'object': title})
    except Exception as error:
      log.append({'function':'compilar_noticias', 'status': str(error), 'object': title})
  return noticias, log

# Define string de busca do google search para sites de noticias
def news(fact, log=log):
  """
  Busca as notícias e retorna query para busca de referencias
  fact deve ser um link válido
  """
  # inicializa notocias
  news = []
  # Buscar notícia
  log.append({'function':'news', 'status':'Buscando notícia fornecida', 'object': fact})
  response = requests.get(fact)
  soup = BeautifulSoup(response.content, 'html.parser')
  texto_da_publicacao = soup.find('div', class_='publicacao-texto')
  try:
    # Tente executar o comando
    # Nos testes vi que muitos sites não tem título definido desta forma...
    title = soup.title.string
    log.append({'function':'news', 'status':'Notícia encontrada', 'object': title})
  except Exception as error:
    # Se ocorrer um erro, execute a ação alternativa
    log.append({'function':'news', 'status':str(error), 'object': fact})
    title = "Noticia"
  text_soup = soup.getText()
  # Ler notícia
  log.append({'function':'news', 'status':'Lendo notícia', 'object': title})
  response = model.generate_content(
      "Transcrever a seguinte sopa de letrinhas no formato do artigo principal contido nela:" + text_soup,
      generation_config=genai.types.GenerationConfig(
        candidate_count=1,
        temperature=0)
      ).text
  news.append({"title": title, "news": response, "source": fact})
  log.append({'function':'news', 'status':'Notícia lida', 'object': title})
  # Gemini cria query para buscar noticias
  print(":Status: Gerando palavras chave para busca...")
  palavras_chave = model.generate_content(
      "Criar um query com palavras-chave para buscar no google search mais notícias relacionadas a este mesmo assunto. Retorne apenas um query, sem nenhum comentário ou explicação. NOTÍCIA:" + response,
      generation_config=genai.types.GenerationConfig(
        candidate_count=1,
        temperature=0.3)
      ).text
  log.append({'function':'news', 'status':'Palavras chaves definidas', 'object': palavras_chave})
  return palavras_chave, news, log

#Define string de busca para fatos relatados
def fact(fact, log=log):
  """
  Cria um query com base na descrição do fato
  """
  log.append({'function':'fact', 'status':'Criando query', 'object':fact})
  palavras_chave = model.generate_content(
      "Criar um query com palavras-chave para buscar no google search notícias relacionadas a este assunto. Retorne apenas as palavras do query, sem usar aspas, sem comentários ou explicação. ASSUNTO:" + fact,
      generation_config=genai.types.GenerationConfig(
        candidate_count=1,
        temperature=0.3)
      ).text
  log.append({'function':'fact', 'status':'Palavras chaves definidas', 'object':palavras_chave})
  return palavras_chave, [], log


# Progrma principal
def main(fact_2_check):
  log = []
  if fact_2_check[0:4] == "http":
    query, noticias, log = news(fact_2_check, log=log)
    fact_2_check = noticias[0]['title']
  else:
    query, noticias, log = fact(fact_2_check, log=log)

  # Busca de noticias
  results, log = search(query, log=log)
  links = listar_links(results)

  # ACionamento do GEMINI para ler e compilar as notícias
  log.append({'function':'main', 'status': 'links para busca', 'object':links})
  noticias, log = compilar_noticias(links, noticias,log=log)

  # Com todas as notícias compiladas na lista notícias, fazer a comparação final
  log.append({'function':'main', 'status': 'Comparando fatos', 'object': noticias})
  prompt = "Baseado nos diferentes textos do campo 'news' e 'title' dos artigos da lista a seguir, você pode opinar sobre se fatos '" + fact_2_check + "' são ou não verdadeiros? Verifique se há consistência entre estes fatos e os damais textos 'news' fornecidos para formar sua opinião. Por favor justificar sua resposta e citar as fontes sempre que possível. Lista: " + str(noticias)
  gen_response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
          candidate_count=1,
          temperature=1.0)
        ).text
  return gen_response, log

# ----------------------------------------------------------------------------
# AQUI EFETIVAMENTE RODAMOS O PROGRAMA
#-----------------------------------------------------------------------------

app = Flask(__name__)

# Configure o CORS para permitir acesso de qualquer origem
CORS(app, resources={r"/": {"origins": "*"}})

@app.route('/', methods=['GET', 'POST'])
def index():
    global NUMERO_DE_DOMINIOS, MAX_REPETICAO
    if request.method == "POST":
        data = request.get_json()
        if data is None:
            return "Invalid JSON format", 400
        if 'dominios' in data:
            NUMERO_DE_DOMINIOS = data.get('dominios')
        if 'max' in data:
            MAX_REPETICAO = data.get('max')
        fact_2_check = data.get('input')
        result, log = main(fact_2_check)
        response = {'response': result, 'logs':log}
    return jsonify(response)
    

if __name__ == '__main__':
    app.run(debug=True)
