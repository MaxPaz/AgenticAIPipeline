# AI Agentic Chat Pipeline

An advanced multi-agent system for intelligent business data querying using AWS Bedrock Agents. This system provides a conversational interface for analyzing business KPIs and transactional data with AI-powered insights and dynamic follow-up questions.

## Features

- 🤖 **Multi-Agent Architecture**: Coordinator, Data Source, Smart Retrieval, and Analysis agents working together
- 💬 **Conversational UI**: Streamlit-based chat interface with real-time streaming responses
- 📊 **Intelligent Data Retrieval**: Automatically determines whether to use KPIs or SQL queries
- 🔍 **Web Search Integration**: Optional Browser Agent for external information retrieval
- 💡 **Dynamic Follow-up Questions**: AI-generated contextual questions based on analysis
- 📈 **Token Usage Tracking**: Real-time visibility into LLM token consumption
- 🎯 **Context-Aware**: Maintains conversation history for natural follow-up queries

## Architecture

### Agent Workflow

```
User Query → Coordinator Agent
              ↓
         Data Source Agent (determines data source)
              ↓
         Smart Retrieval Agent (fetches data via KPIs or SQL)
              ↓
         Analysis Agent (generates insights + suggested questions)
              ↓
         Coordinator Agent (formats response)
              ↓
         User (receives answer + follow-up suggestions)
```

### Components

- **Coordinator Agent**: Orchestrates the entire workflow and manages context
- **Data Source Agent**: Analyzes questions to determine optimal data source
- **Smart Retrieval Agent**: Autonomously retrieves data from KPIs or database
- **Analysis Agent**: Interprets results and generates business insights
- **Browser Agent** (Optional): Performs web searches using AWS Nova Act

## Project Structure

```
.
├── agents/                    # Agent implementations and instructions
│   ├── coordinator_instructions.txt
│   ├── analysis/
│   ├── data_source/
│   └── smart_retrieval/
├── lambda/                    # AWS Lambda functions
│   ├── get_available_kpis/   # KPI metadata retrieval
│   ├── get_kpi_data/         # KPI data retrieval
│   └── sql_executor/         # SQL query execution
├── infrastructure/            # AWS CDK infrastructure code
│   └── cdk/
├── ui/                       # Streamlit user interface
│   └── app.py
├── Browser Agent/            # Web search integration (optional)
├── config/                   # Configuration utilities
├── tools/                    # Metadata loader tools
├── database/                 # Database setup scripts
├── requirements.txt          # Python dependencies
└── .env.example             # Environment template
```

## Prerequisites

- Python 3.9+
- AWS Account with Bedrock access
- AWS CLI configured
- Node.js and AWS CDK (for infrastructure deployment)
- MySQL/PostgreSQL database (for transactional data)

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd AWS_chat
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and configure:
- `AWS_REGION`: Your AWS region (e.g., us-west-2)
- `BEDROCK_AGENT_ID`: Your Bedrock Coordinator Agent ID
- `BEDROCK_AGENT_ALIAS_ID`: Your Bedrock Agent Alias ID
- Database connection details (if using transactional data)

### 3. Deploy Infrastructure

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed deployment instructions.

```bash
cd infrastructure/cdk
cdk deploy
```

### 4. Launch UI

```bash
streamlit run ui/app.py
```

The UI will be available at `http://localhost:8501`

## Configuration

### Required Environment Variables

```bash
# AWS Configuration
AWS_REGION=us-west-2

# Bedrock Agent Configuration
BEDROCK_AGENT_ID=your_agent_id
BEDROCK_AGENT_ALIAS_ID=your_alias_id

# Database Configuration (optional)
DB_HOST=your_db_host
DB_PORT=3306
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
```

### Optional Features

**Web Search (Browser Agent)**:
- Set `BROWSER_AGENT_ARN` in `.env`
- See `Browser Agent/README.md` for setup instructions

## Usage

### Example Queries

```
"What were the total sales last month?"
"Compare revenue between Q1 and Q2 in 2023"
"Show me the top 5 customers by revenue"
"What were the monthly trends for Customer A?"
```

### Features

1. **Dynamic Follow-up Questions**: After each response, the system suggests relevant follow-up questions
2. **Token Usage Tracking**: View token consumption for each query in the workflow expander
3. **Web Search Mode**: Toggle between internal data and web search
4. **Session Management**: Conversations maintain context across multiple queries

## Development

### Running Tests

```bash
pytest
```

### Deploying Agent Updates

```bash
# Deploy coordinator
cd agents
./deploy_coordinator.sh

# Deploy individual agents
cd agents/analysis
./deploy.sh
```

### Viewing Logs

CloudWatch logs are available at:
- Log Group: `BedrockLogging`
- Contains model invocations and token usage

## Architecture Details

For detailed architecture information, see [BEDROCK_AGENT_ARCHITECTURE.md](BEDROCK_AGENT_ARCHITECTURE.md)

### Key Design Decisions

- **JSON Response Format**: Coordinator returns structured JSON for reliable parsing
- **Context Summarization**: Prevents token explosion in long conversations
- **Autonomous Retrieval**: Smart Retrieval Agent decides between KPIs and SQL
- **Token Tracking**: CloudWatch integration for cost visibility

## Troubleshooting

### Common Issues

**"Agent not found" error**:
- Verify `BEDROCK_AGENT_ID` and `BEDROCK_AGENT_ALIAS_ID` in `.env`
- Ensure agent alias points to the latest version

**Token usage shows 0**:
- CloudWatch logs may have a delay (wait 30-60 seconds)
- Verify CloudWatch logging is enabled for Bedrock

**Suggested questions not appearing**:
- Ensure coordinator agent is using the latest instructions
- Check that agent alias is updated after deployment

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## Support

For issues or questions, please contact the development team.
