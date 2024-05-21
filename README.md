# GEMINI-fact-checker
Fact checking LLM with continuous deplymento to cloud

A verificação de fatos consiste em uma série de agentes LLM Gemini que executam a seguinte sequencia de atividades:

![image](https://github.com/nikinuk/GEMINI-fact-checker/assets/141849141/9a27ab80-f151-4a29-9f28-e4d38ee11f16)

O usuário pode iniciar o processo descrevendo um fato a ser verificado ou colando a URL de um fato noticiado. No segundo caso, o primeiro agente interpreta a notícia para estabelecer o fato. Com o fato estabelecido, passa para o segundo agente queestabelece as palavras chaves para a busca por mais informação.
O terceiro agente efetua a busca (não por LLM, mas um serviço do google search) e seleciona os links para a pesquisa. O quarto agente faz a leitura de cada site de notícias para fornecer uma lista de fatos e notícias ao quinto agente. Este faz a comparação do fato relatado ou extraúdo do URL inicial explicando suas conclusões co bas nas evidências coletadas nos sites de busca. O sexto e último agente formata a conclusão para apresentação no formato HTML.

A ferramenta é configurada atravéz de um JSON de configuração que deve ser postado no momento da chamada. A configuração inclui:
- Lista de endereços onde a busca deve ser efetuada (domínios de confiançã) - se não há preferências, uma lista vazia é passada e o agente de buca faz uma busca em toda internet.
- Número máximo de domínios de busca: quantos sites queremos ler.
- Número máximos de domínios repetidos: a busca pode resultar em múltiplas notícias de um mesmo portal, para efeito de verificação de fatos, podemos restringir para evitar que mesma fonte seja utilizada.
- Janela temporal: quantos dias, semanas, meses ou anos em retrospectiva queremos incluir na busca: para fatos específicos ocorridos em data conhecida, melhor limitar a janela de busca.

O serviço está rodando em um "Cloud Run" do Google Cloud e é solicitado pelo link: https://fact-check-inspiria-32mkcjubia-rj.a.run.app
Temos dois end-points, um para o POST ("/") e outro para obter o status dos agentes ("/progress/task")
O arquivo de configuração deve seguir a seguinte formatação:

{ 

'input': str, #fato ou url

'num_dominios': int, 

'max': int,

'time_window': str, # timeUnit (d/w/m/y) + int, ex, duas semanas = w2

'dominios': [str], lista de domínios no formato "www.dominio.com"

}
