import requests
import google.generativeai as genai
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import shared_memory

GOOGLE_API_KEY = "AIzaSyBzbl55y2JDsxPRpmgTcAsbcGkwyydRXY0"
CLOUD_KEY = "AIzaSyAVofiTa9nyTjxTufNtBnOKZpWqytzpWpA"
CX = "d3d2555aa63924e2a"

URL = "https://www.googleapis.com/customsearch/v1"

DATE_RESTRICTION = "m3"

NUMERO_DE_DOMINIOS = 5 # Numeros de dominios de busca para usar (quanto mais, melhor, porém mais demorado e com maior consumo de tokens)
MAX_REPETICAO = 2 # Numero máximos de repetições aceitas de links em mesmo domínio. Pouco adianta comparar 5 notícias de um mesmo portal

NUBER_OF_RESULTS = NUMERO_DE_DOMINIOS * MAX_REPETICAO * 2

DOMINIOS_DE_BUSCA = [
    "exame.com",
    "www.cnnbrasil.com.br",
    "www.cartacapital.com.br",
    "www.poder360.com.br",
    "www.bbc.com",
    "www.poder360.com.br",
    "g1.globo.com",
    "oglobo.globo.com" # Até aqui coloquei sites de notícias abertos
    "www.in.gov.br",
    "www12.senado.leg.br",
    "www.camara.leg.br",
    "www.gov.br",
    "www.cnj.jus.br", # Até aqui inclui sites oficiais mais importantes do governo federal.
    "agenciabrasil.ebc.com.br",
    "noticias.uol.com.br",
    "checamos.afp.com",
    "lupa.uol.com.br",
    "www.boatos.org",
    "projetocomprova.com.br",
    "www.e-farsas.com" # Até aqui incluí portais de verifcações de fatos profissionais, para caso a notícia já tenha sido verificada.
]

#Inicialização do modelo GEMINI
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.0-pro')

log=[]

def custom_search(query, domains = DOMINIOS_DE_BUSCA, n=5, r=2, date_restriction = "w3", api_key=CLOUD_KEY, cse_id=CX, log=log):
  """
  This function performs a custom search using Google Custom Search API 
  and incorporates a domain whitelist and result filtering.

  Args:
      domains: List of desired domains (strings).
      n: Maximum number of desired results (integer).
      r: Maximum allowed repetitions from each domain (integer).
      query: Search query string.
      api_key: Your Google Custom Search API key (string).
      cse_id: Your Google Custom Search Engine ID (string).

  Returns:
      A list of filtered search results (strings).
  """

  # Base URL for the Google Custom Search JSON API
  base_url = "https://www.googleapis.com/customsearch/v1"

  # Build the request parameters
  params = {
    'q': query, 
    'key': api_key, 
    'cx': cse_id, 
    'dateRestrict': date_restriction, 
    }

  # Final list to store filtered URLs
  filtered_results = []

  if len(domains)>0:
    domain_counts = {domain: 0 for domain in domains}  # Track domain repetitions
  else:
    domain_counts = {}

  while len(filtered_results) < n:
    # Make a request to the API
    response = requests.get(base_url, params=params)
    
    if response.ok:
      # Parse JSON response
      data = response.json()

      # Loop through retrieved search results
      if 'items' in data:
        for item in data['items']:
          # Extract URL and domain
          url = item['link']
          domain = url.split("//")[1].split("/")[0]

          # Check if domain is in the whitelist and repetition limit not reached
          if len(domains)>0:
            if domain in domains and domain_counts[domain] < r:
              filtered_results.append(url)
              domain_counts[domain] += 1  # Increment domain count
          else:
            if domain in domain_counts:
              if domain_counts[domain] < r:
                filtered_results.append(url)
                domain_counts[domain] += 1
            else:
              domain_counts[domain] = 1
              filtered_results.append(url)

          if len(filtered_results) == n: # Exit loop if desired results reached
            break
      else:
        filtered_results.append("www.google.com")
        log.append({'function':'query', 'status': "NOK - found NO links", 'object': str(filtered_results)})
        return filtered_results, log

      # Handle case where enough results not found from whitelisted domains
      if len(filtered_results) < n and 'nextPage' in data['queries']:
        params['start'] = data['queries']['nextPage'][0]['startIndex']
      else:
        break  # Exit loop if no more pages or insufficient results
    else:
      filtered_results.append("ERROR")
      log.append({'function':'query', 'status': "NOK - error on query", 'object': str(filtered_results)})
      return filtered_results, log
  
  log.append({'function':'query', 'status': "OK found " + str(len(filtered_results)) + " links", 'object': str(filtered_results)})
  
  return filtered_results, log

def clean_spaces(text):
    # Remove leading and trailing spaces
    text = text.strip()
    # Replace multiple spaces with a single space
    text = ' '.join(text.split())
    return text

def extrair_dominio(url):
    dominio_principal = url.split("//")[1].split("/")[0]
    return dominio_principal

def create_shared_memory():
  # Define the size of the shared memory block
  shm_size = 1024
  # Create the shared memory block
  try:
    shm = shared_memory.SharedMemory(name='progress_message', create=True, size=shm_size)
  except FileExistsError:
    shm = shared_memory.SharedMemory(name='progress_message', create=False, size=shm_size)
  # Define a structure within the memory block (replace with your data format)
  class ProgressMessage:
    def __init__(self, message):
      self.message = message
  # Get a buffer object to access the shared memory
  buffer = shm.buf
  # Create a ProgressMessage instance at the beginning of the buffer
  progress_message = ProgressMessage("")
  return shm, buffer, progress_message

# Usar Gemini para compilar textos
def compilar_noticias(links, noticias, log=log):
  """
  Le as notícias usando o Gemini e retorna JSON com titulo, conteudo e fonte
  """
  noticias = []
  i = 0
  j = str(len(links))
  for url in links:
    i=i+1
    log.append({'function':'compilar_noticias', 'status': 'LENDO URL', 'object': url})
    progress_message.message = str(i) + "/" + j + "-LENDO URL: " + url
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    try:
      # Tente executar o comando
      # Nos testes vi que muitos sites não tem título definido desta forma...
      title = clean_spaces(soup.title.string)
      log.append({'function':'compilar_noticias', 'status': 'NOTICIA ENCONTRADA', 'object': title})
      progress_message.message = str(i) + "/" + j + "-NOTICIA ENCONTRADA: " + title
    except Exception as error:
      # Se ocorrer um erro, execute a ação alternativa
      log.append({'function':'compilar_noticias', 'status': str(error), 'object': url})
      progress_message.message = str(i) + "/" + j + "-ERROR AO COMPILAR URL " + url
      title = "Noticia"
    text_soup = soup.getText()
    try:
      progress_message.message = str(i) + "/" + j + "-LENDO NOTÍCIA " + title
      gen_response = model.generate_content(
          "Transcrever o artigo escrito em meio à sopa de letras e codigos:" + text_soup,
          generation_config=genai.types.GenerationConfig(
            candidate_count=1,
            temperature=0) # Temperatura zero pois a rede não deve criar, apenas transcrever
          ).text
      noticias.append({"title": title, "news": gen_response, "source": url})
      log.append({'function':'compilar_noticias', 'status': 'NOTICIA LIDA COM SUCESSO', 'object': title})
      progress_message.message = str(i) + "/" + j + "-NOTICIA LIDA COM SUCESSO: " + title
    except Exception as error:
      log.append({'function':'compilar_noticias', 'status': str(error), 'object': title})
      progress_message.message = str(i) + "/" + j + "-ERRO NA LEITURA DA NOTICIA: " + title
  return noticias, log

# Define string de busca do google search para sites de noticias
def news(fact, log=log):
  """
  Busca as notícias e retorna query para busca de referencias
  fact deve ser um link válido
  """
  # Buscar notícia
  log.append({'function':'news', 'status':'BUSCANDO URL', 'object': fact})
  progress_message.message = 'BUSCANDO URL: ' + fact
  response = requests.get(fact)
  soup = BeautifulSoup(response.content, 'html.parser')
  try:
    # Tente executar o comando
    # Nos testes vi que muitos sites não tem título definido desta forma...
    title = clean_spaces(soup.title.string)
    log.append({'function':'news', 'status':'NOTICIA ENCONTRADA', 'object': title})
    progress_message.message = 'NOTICIA ENCONTRADA: ' + title
  except Exception as error:
    # Se ocorrer um erro, execute a ação alternativa
    log.append({'function':'news', 'status':str(error), 'object': fact})
    progress_message.message = "ERRO DE TITULO: " + str(error)
    title = "Noticia"
  text_soup = soup.getText()
  # Ler notícia
  log.append({'function':'news', 'status':'LENDO NOTICIA', 'object': title})
  progress_message.message = 'LENDO NOTICIA: ' + title
  response = model.generate_content(
      "Transcrever a seguinte sopa de letrinhas no formato do artigo principal contido nela:" + text_soup,
      generation_config=genai.types.GenerationConfig(
        candidate_count=1,
        temperature=0)
      ).text
  fact_2_check = title + ": " + response
  log.append({'function':'news', 'status':'NOTICIA LIDA COM SUCESSO', 'object': title})
  progress_message.message = "CRIANDO CRITERIO DE BUSCA PARA: " + title
  # Gemini cria query para buscar noticias
  palavras_chave = model.generate_content(
      "Criar um query com palavras-chave para buscar no google search mais notícias relacionadas a este mesmo assunto. Retorne apenas um query, sem nenhum comentário ou explicação. NOTÍCIA:" + response,
      generation_config=genai.types.GenerationConfig(
        candidate_count=1,
        temperature=0.3)
      ).text
  progress_message.message = "CRITERIO DE BUSCA DEFINIDO: " + palavras_chave
  log.append({'function':'news', 'status':'CRITERIO DE BUSCA DEFINIDO', 'object': palavras_chave})
  return palavras_chave, fact_2_check, log

#Define string de busca para fatos relatados
def fact(fact_2_check, log=log):
  """
  Cria um query com base na descrição do fato
  """
  log.append({'function':'fact', 'status':'CRIANDO CRITERIO DE BUSCA', 'object':fact_2_check})
  progress_message.message = "CRIANDO CRITERIO DE BUSCA PARA FATOS NARRADOS"
  palavras_chave = model.generate_content(
      "Criar um query com palavras-chave para buscar no google search notícias relacionadas a este assunto. Retorne apenas as palavras do query, sem usar aspas, sem comentários ou explicação. ASSUNTO:" + fact_2_check,
      generation_config=genai.types.GenerationConfig(
        candidate_count=1,
        temperature=0.3)
      ).text
  log.append({'function':'fact', 'status':'CRITERIO DE BUSCA DEFINIDO', 'object':palavras_chave})
  progress_message.message = "CRITERIO DE BUSCA DEFINIDO: " + palavras_chave
  return palavras_chave, fact_2_check, log


# Progrma principal
def main(fact_2_check):
  log = []
  progress_message.message = "INICIANDO VERIFICAÇÃO..."
  if fact_2_check[0:4] == "http":
    query, fact_2_check, log = news(fact_2_check, log=log)
  else:
    query, fact_2_check, log = fact(fact_2_check, log=log)

  # Busca de noticias
  progress_message.message = "EXECUTANDO BUSCA"
  links, log = custom_search(query, domains=DOMINIOS_DE_BUSCA, n=NUMERO_DE_DOMINIOS, r=MAX_REPETICAO,date_restriction=DATE_RESTRICTION)

  if len(links)>1:
      # ACionamento do GEMINI para ler e compilar as notícias
      log.append({'function':'main', 'status': 'URLS FONTE ENCONTRADAS', 'object':links})
      progress_message.message = "URLS FONTE ENCONTRADAS: " + str(len(links))

      noticias, log = compilar_noticias(links, fact_2_check ,log=log)

      # Com todas as notícias compiladas na lista notícias, fazer a comparação final
      log.append({'function':'main', 'status': 'AVALIANDO FATOS', 'object': noticias})
      progress_message.message = "AVALIANDO FATOS..."
      prompt = f"""
      Você é um assistente de jornalismo investigativo de verificação de fatos.
      Opinar sobre se fatos '{fact_2_check}' são verdadeiros ou duvidosos? 
      Para formar sua opinião, verifique se há consistência entre estes fatos e os damais fatos narrados nos textos 'news' fornecidos na lista a seguir. Por favor justificar sua resposta e citar as fontes (urls) sempre que possível. 
      Lista: {str(noticias)}
      """
      gen_response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
              candidate_count=1,
              temperature=1.0)
            ).text
  else:
     gen_response = f"Não foram encontradas suficientes fontes em a respeirto do tema."
  return gen_response, log, noticias
  
     
def formatar_resposta(texto):
  progress_message.message = "FORMATANDO RESPOSTA FINAL..."
  prompt = f"""
  Formatar o texto a seguir usando apenas TAGs HTML, de forma que possa ser corretamente apresentado em um <div> dinamico de uma pagiga HTML, conforme exemplo apresentado:
  
  ### Exemplo: 
  #Texto (exemplo): 
  **Verificação de Fatos sobre o "Cavalo Caramelo Resgatado no RS"** **Fatos Consistentes:** * Um cavalo ficou preso em um telhado em Canoas, Rio Grande do Sul. * O cavalo ficou conhecido como "Caramelo" devido ao apelido dado por usuários das redes sociais. * Bombeiros de São Paulo resgataram o cavalo, que foi sedado e colocado em um bote. * O animal ficou ilhado por pelo menos 24 horas sem comida ou água. **Referências:** * [G1](https://g1.globo.com/rs/rio-grande-do-sul/noticia/2024/05/09/resgate-do-cavalo-caramelo-entenda-como-animal-foi-retirado-de-cima-do-telhado-no-rs.ghtml) * [CNN Brasil](https://www.cnnbrasil.com.br/internacional/resgate-do-cavalo-caramelo-no-rs-repercute-na-imprensa-internacional-veja/) **Conclusão:** Os fatos relatados sobre o resgate do "Cavalo Caramelo" são **consistentes** com as informações fornecidas nos textos de notícias fornecidos. Não há informações que contradigam ou coloquem em dúvida a veracidade desses fatos.
  
  #HTML (exemplo): 
  <strong>Verificação de Fatos sobre o "Cavalo Caramelo Resgatado no RS"</strong>
  <strong>Fatos Consistentes:</strong>
    <ul>
        <li>Um cavalo ficou preso em um telhado em Canoas, Rio Grande do Sul.</li>
        <li>O cavalo ficou conhecido como "Caramelo" devido ao apelido dado por usuários das redes sociais.</li>
        <li>Bombeiros de São Paulo resgataram o cavalo, que foi sedado e colocado em um bote.</li>
        <li>O animal ficou ilhado por pelo menos 24 horas sem comida ou água.</li>
    </ul>
    <strong>Referências:</strong>
    <ul>
        <li><a href="https://g1.globo.com/rs/rio-grande-do-sul/noticia/2024/05/09/resgate-do-cavalo-caramelo-entenda-como-animal-foi-retirado-de-cima-do-telhado-no-rs.ghtml">G1</a></li>
        <li><a href="https://www.cnnbrasil.com.br/internacional/resgate-do-cavalo-caramelo-no-rs-repercute-na-imprensa-internacional-veja/">CNN Brasil</a></li>
    </ul>
    <strong>Conclusão:</strong> Os fatos relatados sobre o resgate do "Cavalo Caramelo" são <strong>consistentes</strong> com as informações fornecidas nos textos de notícias fornecidos. Não há informações que contradigam ou coloquem em dúvida a veracidade desses fatos.
    </div>

    #Texto:
    {texto}
    #HTML:
  """
  gen_response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
          candidate_count=1,
          temperature=0)
        ).text
  progress_message.message = "FINALIZADO"
  return gen_response

shm, buffer, progress_message = create_shared_memory()

# ----------------------------------------------------------------------------
# AQUI EFETIVAMENTE RODAMOS O PROGRAMA
#-----------------------------------------------------------------------------

app = Flask(__name__)

executor = ThreadPoolExecutor(max_workers=1)

# Configure o CORS para permitir acesso de qualquer origem
CORS(app, resources={
   r"/": {"origins": "*"}, 
   r"/progress/task": {"origins": "*"}
   })

@app.route('/', methods=['GET', 'POST'])
def index():
    
    global task_id
    global NUMERO_DE_DOMINIOS, MAX_REPETICAO, DOMINIOS_DE_BUSCA, DATE_RESTRICTION
    if request.method == "POST":
        data = request.get_json()
        if data is None:
            return "Invalid JSON format", 400
        if 'dominios' in data:
            NUMERO_DE_DOMINIOS = data.get('num_dominios')
        if 'max' in data:
            MAX_REPETICAO = data.get('max')
        if 'dominios' in data:
            DOMINIOS_DE_BUSCA = data.get('dominios')
        if 'time_window' in data:
            DATE_RESTRICTION = data.get('time_window')

        fact2check = data.get('input')

        progress_message.message = f"FACT2CHECK: {fact2check} \nNum. de domínios: {NUMERO_DE_DOMINIOS}\nRepetição de domínios: {MAX_REPETICAO}"
        task_id = executor.submit(main, fact2check)
        result, log, noticias = task_id.result()

        result = formatar_resposta(result)

        source = "<p>"
        i = 1
        for new in noticias:
           source = source + str(i) + '. ' + new['title'][0:80] + '... : <a href="' + new['source'] + '"> ' + extrair_dominio(new['source']) + ' </a><br>'
           i=i+1 
        source = source + '</p>'
        
    return jsonify({'response': result, 'logs': str(log), 'source': source })

@app.route("/progress/task")
def get_progress():
  return jsonify({'progress': progress_message.message})


if __name__ == '__main__':
    app.run(debug=True)
