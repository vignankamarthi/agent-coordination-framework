# Personalized Course Recommendation System

An AI-powered recommendation system designed for the Northeastern University community, specifically targeting students and professionals transitioning into Data Science and AI roles. This system combines sophisticated machine learning approaches with real-time market analysis to deliver personalized educational pathways.

## Overview

The system implements a multi-agent architecture that intelligently routes user queries through specialized recommendation engines based on intent classification. Each query is processed through one of three distinct pathways, ensuring optimal recommendation quality and relevance.

### AI Engineering Pipeline

The core architecture employs LangGraph for orchestration, managing workflow state and routing user queries to appropriate specialized agents:

![AI Engineering Pipeline](docs/flow_diagrams/AI_Engineering_Pipeline.png)

The orchestrator performs intent classification using Cohere's LLM to determine whether a query requires database lookup, collaborative filtering, or content-based analysis, then routes accordingly through the appropriate agent workflow.

### Content-Based Recommendation Engine

For queries about trending skills, job market insights, and research-backed recommendations, the Content Agent integrates multiple data sources:

![Content-Based Recommendation Agent](docs/flow_diagrams/Content_Agent_Flow.png)

This agent processes uploaded resumes, performs web searches via Tavily for real-time market data, and utilizes a research paper vector store to provide evidence-based course recommendations with robust academic context.

### Collaborative Filtering Engine

For personalized learning path recommendations, the Collaborative Agent analyzes user similarity patterns stored in Neo4j:

![Collaborative Filtering-Based Recommendation Agent](docs/flow_diagrams/Collaborative_Filtering_Agent_Flow.jpg)

By generating user vectors from profile data and finding similar learners, this engine recommends courses based on successful learning patterns of users with similar backgrounds and goals.

## Key Features

- **Intent-Aware Routing**: Intelligent query classification directs users to the most appropriate recommendation agent
- **Multi-Modal Input Processing**: Supports resume analysis (PDF/DOCX) alongside natural language queries
- **Real-Time Market Intelligence**: Integration with Tavily API for current job trends and skill demands
- **Research-Backed Recommendations**: Vector store of academic papers provides evidence-based course suggestions
- **Collaborative Intelligence**: Neo4j-powered user similarity matching for personalized learning paths
- **Comprehensive Logging**: Structured logging with error handling for production-ready deployment

## Getting Started

### Prerequisites

- Docker and Docker Compose

### 1. Configuration

First, clone the repository and set up your API keys:

```bash
git clone <repository-url>
cd course-recommendation-system/docker
```

Create your environment configuration file from the example:

```bash
cp .env.example .env
```

Edit the `.env` file to add your API keys and credentials:

**Required API Keys:**
- `COHERE_API_KEY` - Your Cohere API key
- `TAVILY_API_KEY` - Your Tavily API key
- `OPENAI_API_KEY` - Your OpenAI API key (required for LangSmith integration)
- `LANGSMITH_API_KEY` - Your LangSmith API key for tracing and observability

**Neo4j Database Access:**
- `NEO4J_PASSWORD` - **Contact repository creators for credentials** to access the full course and user dataset
- Default password provided works but has no data

**Optional Settings:**
- MySQL configuration (defaults work automatically)

Get your API keys from:
- **Cohere**: [dashboard.cohere.ai/api-keys](https://dashboard.cohere.ai/api-keys) for AI/LLM tools/functions. 
- **Tavily**: [app.tavily.com](https://app.tavily.com) for web search capabilities
- **OpenAI**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys) for LangSmith integration
- **LangSmith**: [smith.langchain.com](https://smith.langchain.com) for tracing and debugging

### 2. Start the Application

Once your `.env` file is configured, start the entire application using Docker Compose:

```bash
# Start all containers (MySQL, Neo4j, and the application)
docker compose up

# In another terminal, verify all containers are running
docker compose ps
```

**Important:** Run without `-d` flag to see real-time logs in your terminal. This is essential for development and debugging. Use a separate terminal tab for other commands. See the [Logging System](#logging-system) section for more details about logs.

**Note:** Docker handles ALL dependencies automatically - no local Python installation or virtual environment needed. The application container includes all required Python packages.

### 3. Access Web Interfaces

Once running, you can access these web-based services:

- **Main Application**: [http://localhost:7860](http://localhost:7860) - Gradio interface for course recommendations
- **Neo4j Browser**: [http://localhost:7474](http://localhost:7474) - Graph database interface to explore user relationships and data
- **MySQL** (if needed): Connect via your preferred MySQL client to `localhost:3306`

**Neo4j Login**: Use username `neo4j` and the password you set in your `.env` file (default: `neo4jpassword`)

## Developer Tools

### LangSmith MCP Integration

The project includes Model Context Protocol integration for LangSmith development tools. This provides direct access to dataset management, evaluation testing, and debugging traces through Claude Desktop during development.

**Setup**:
1. Ensure your `LANGSMITH_API_KEY` is configured in `docker/.env`
2. Source the MCP environment setup script:
   ```bash
   source .mcp/setup-mcp.sh
   ```
   This script automatically pulls the LangSmith API key from your Docker environment file, maintaining a single source of truth.

3. Configure Claude Desktop with the MCP server settings (see [.mcp/README.md](.mcp/README.md))

**Detailed Documentation**: See [.mcp/README.md](.mcp/README.md) for complete MCP tools documentation and usage examples.

### Logging System

The system implements a comprehensive logging structure via `SystemLogger`. Logs are printed to the console output of the Docker container, making them available in real-time when running the container in attached mode (without detached mode).

```python
from utils.logger import SystemLogger

# Different log levels with automatic context
SystemLogger.info("Processing user query", {
    'user_id': user_id,
    'query_preview': query[:50]
})

SystemLogger.error("Database connection failed", 
    exception=e,
    context={'connection_attempt': attempt_count}
)
```

**Log Hierarchy**: `DEBUG` → `INFO` → `ERROR` with automatic file rotation in `logs/` directory.

### Error Handling

Structured exception handling with custom exception types:

```python
from utils.exceptions import WorkflowError, APIRequestError

try:
    result = process_query(query)
except APIRequestError as e:
    SystemLogger.error("External API failure", exception=e)
    return fallback_response()
```

**Available Exceptions**: `WorkflowError`, `AgentExecutionError`, `APIRequestError`, `DatabaseConnectionError`, `ConfigurationError`

### LangSmith Observability

The system integrates LangSmith for comprehensive tracing and debugging across all workflows:

```python
# Automatic tracing of agent workflows and LLM calls
LANGSMITH_API_KEY=your-langsmith-api-key-here
LANGCHAIN_PROJECT=IMPEL
```

**Traced Components**: Intent classification, multi-agent workflows (Database, Collaborative, Content), LLM interactions, similarity searches, and state transitions.

**Dashboard Access**: View traces at [smith.langchain.com](https://smith.langchain.com) for debugging agent decisions and performance monitoring.

## Architecture Details

- **Orchestrator**: LangGraph-based workflow management with state persistence
- **Database Layer**: MySQL for course data, Neo4j for user interactions and similarity graphs
- **Vector Stores**: FAISS for course similarity, research paper retrieval
- **LLM Integration**: Cohere for intent classification and response generation
- **Web Interface**: Gradio for user interaction with file upload support

## Future Explorations

### Prompt Engineering with LangSmith

The integrated LangSmith observability enables systematic prompt optimization through data-driven approaches:

- **A/B Testing Framework**: Use LangSmith's evaluation datasets to compare prompt variations across agent workflows, measuring recommendation quality and user satisfaction metrics
- **Prompt Optimization Tools**: Leverage LangSmith's prompt engineering interface for real-time testing of intent classification, content generation, and collaborative filtering prompts
- **Performance Monitoring**: Track prompt effectiveness through LangSmith dashboards, identifying patterns in successful versus failed recommendations to guide iterative improvements
- **Multi-Agent Prompt Coordination**: Optimize prompt handoffs between DatabaseAgent, ContentAgent, and CollaborativeAgent using trace data to reduce context loss and improve workflow coherence

### Model Fine-Tuning and Domain Adaptation

With comprehensive tracing data from LangSmith, the system supports advanced model customization:

- **Educational Domain Fine-Tuning**: Utilize collected user interaction patterns and successful recommendation traces to fine-tune models on course recommendation tasks using parameter-efficient methods like LoRA/QLoRA
- **Evaluation-Driven Training**: Use LangSmith's evaluation frameworks to create training datasets from high-quality recommendation traces, ensuring fine-tuned models maintain or exceed baseline performance

### Weight-Level Modifications and Architecture Optimization

Deep system optimization using LangSmith trace analysis:

- **Intent Classification Improvements**: Analyze misclassification patterns from LangSmith traces to guide architecture modifications for better query understanding and sub-agent routing
- **Multi-Agent Communication**: Optimize embedding layers and attention mechanisms based on successful agent interaction patterns captured in traces
- **State Representation Learning**: Use LangGraph state transition data to improve vector representations for user preferences and course similarities
- **Performance-Driven Architecture**: Identify computational bottlenecks through LangSmith performance metrics to guide architectural decisions for latency-sensitive recommendation generation

### MCP Application Integration

Extend the current LangSmith MCP documentation server to include application-level integrations:

- **Course Recommendation Tools**: Develop MCP servers providing direct access to course search, recommendation generation, and user interaction data for AI assistant integration
- **Multi-Agent System Access**: Create MCP tools for DatabaseAgent, CollaborativeAgent, and ContentAgent workflows, enabling Claude's CLI to utilize the recommendation pipeline for efficeient, iterative development workflow structures
- **Developer Productivity**: Implement MCP servers for system debugging, evaluation dataset creation, and performance monitoring to enable iterative development workflows

## License

This project is licensed under the MIT License.