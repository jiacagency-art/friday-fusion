# Engines

Esta pasta contém os engines externos clonados. **Não estão incluídos no repositório git** (ver `.gitignore`) — devem ser clonados separadamente.

## Clonar todos os engines

```bash
cd engines
git clone --depth 1 https://github.com/browser-use/browser-use.git
git clone --depth 1 https://github.com/camel-ai/owl.git
git clone --depth 1 https://github.com/All-Hands-AI/OpenHands.git
git clone --depth 1 https://github.com/google/adk-python.git google-adk
git clone --depth 1 https://github.com/microsoft/autogen.git
git clone --depth 1 https://github.com/crewAIInc/crewAI.git crewai
git clone --depth 1 https://github.com/langchain-ai/langgraph.git
git clone --depth 1 https://github.com/huggingface/smolagents.git
git clone --depth 1 https://github.com/camel-ai/camel.git
git clone --depth 1 https://github.com/anthropics/anthropic-quickstarts.git
```

## Activar um engine

Cada engine tem as suas dependências. Ver o README de cada um. Em geral:

```bash
cd engines/<engine>
pip install -e .
```

Variáveis de ambiente necessárias:
- Browser Use, OWL, Google ADK, smolagents, Camel: `GEMINI_API_KEY` ou `OPENAI_API_KEY`
- OpenHands: Docker daemon a correr
- Anthropic CUA: `ANTHROPIC_API_KEY` + Docker (para a demo completa)
