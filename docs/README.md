# Documentation Index

Welcome to the Contract Analysis system documentation. This directory contains comprehensive guides for understanding, configuring, and using the system.

## 📚 Documentation Overview

### Core Documentation

| Document                                          | Description                                                   | Audience                      |
| ------------------------------------------------- | ------------------------------------------------------------- | ----------------------------- |
| **[APPROACH.md](APPROACH.md)**                 | System architecture, philosophy, and template integration | Technical teams, architects   |
| **[API.md](API.md)**                           | Complete API reference for all components                     | Developers, integrators       |
| **[CONFIGURATION.md](CONFIGURATION.md)**       | Configuration options and setup guide                         | System administrators, DevOps |
| **[LOGGING.md](LOGGING.md)**                   | Logging, debugging, and troubleshooting                       | Support teams, developers     |
| **[workflow_diagram.md](workflow_diagram.md)** | Visual workflow with multi-critic architecture                | All users                     |
| **[critic_agent_opportunities.md](critic_agent_opportunities.md)** | Critic agents design and implementation status | Architects, developers        |

### Quick Navigation

#### 🚀 **Getting Started**

- New to the system? Start with the main [README.md](../README.md)
- Want to understand the architecture? Read [APPROACH.md](APPROACH.md)
- Need to configure the system? Check [CONFIGURATION.md](CONFIGURATION.md)

#### 🔧 **Development & Integration**

- API integration: [API.md](API.md)
- Debugging issues: [LOGGING.md](LOGGING.md)
- Workflow understanding: [workflow_diagram.md](workflow_diagram.md)

#### 🏢 **Template Features**

- Template structure and Y/N extraction: [APPROACH.md#template-integration](APPROACH.md#template-integration)
- Excel output configuration: [CONFIGURATION.md#template-configuration](CONFIGURATION.md#template-configuration)
- Template API reference: [API.md#template-integration](API.md#template-integration)

#### 🛡️ **Multi-Critic Architecture**

- Workflow with critics: [workflow_diagram.md](workflow_diagram.md)
- Critic design and opportunities: [critic_agent_opportunities.md](critic_agent_opportunities.md)
- Configuration: [CONFIGURATION.md#critic-configuration](CONFIGURATION.md#critic-configuration)

## 🎯 Key Features Covered

### System Architecture

- **Classification-First Approach**: 99% token reduction through smart sentence processing
- **Dual Model Validation**: Granite + Mixtral cross-validation for quality assurance
- **Agentic Workflow**: LangGraph orchestration with state management
- **Template Integration**: Professional Excel output with Y/N determinations
- **Multi-Critic Architecture**: 8 comprehensive critic agents for self-healing and quality assurance

### Technical Implementation

- **API Integration**: Granite and Ollama/Mixtral model integration
- **State Management**: Comprehensive workflow state tracking
- **Error Handling**: Robust error recovery and logging
- **Output Generation**: Multi-format outputs with template support

### Quality Assurance

- **Comprehensive Logging**: Complete audit trail and debugging capabilities
- **Model Comparison**: Agreement analysis between models
- **Quality Metrics**: Confidence scoring and processing statistics
- **Professional Output**: compliant Excel templates
- **Critic Agents**: Self-healing workflow with automatic issue detection and retry logic
  - PDF Conversion Quality Critic
  - Entity Extraction Completeness Critic
  - Classification Coverage Critic
  - Cross-Document Consistency Critic
  - Rule Compliance Logic Critic
  - Questionnaire Completeness Critic
  - Citation Critic
  - Final Output Sanitization Critic

## 📖 Documentation Standards

### Code Examples

All documentation includes:

- **Working code examples** with proper imports
- **Configuration snippets** with realistic values
- **Command-line examples** with expected outputs
- **Error handling patterns** for common issues

### Cross-References

- Links between related topics across documents
- Consistent terminology and naming conventions
- Version information for API changes
- Prerequisites and dependencies clearly stated

## 🔄 Keeping Documentation Updated

### Automatic Updates

- **Workflow diagrams** are generated using LangGraph's built-in capabilities
- **State logging examples** reflect actual log formats
- **API examples** are tested with real implementations

### Manual Updates

When making changes to the system:

1. Update relevant documentation sections
2. Test all code examples
3. Update version information if applicable
4. Cross-check references between documents

## 🤝 Contributing to Documentation

### Style Guidelines

- Use clear, concise language
- Include practical examples
- Maintain consistent formatting
- Add diagrams for complex concepts

### Review Process

- Technical accuracy review by development team
- Usability review by end users
- Regular updates with system changes
- Feedback incorporation from user questions

## 📞 Support and Feedback

### Getting Help

- **Technical Issues**: Check [LOGGING.md](LOGGING.md) for debugging guidance
- **Configuration Problems**: Refer to [CONFIGURATION.md](CONFIGURATION.md)
- **API Questions**: Consult [API.md](API.md)
- **General Questions**: Start with main [README.md](../README.md)

### Providing Feedback

- Documentation improvements
- Missing information identification
- Example requests
- Clarity suggestions

---

This documentation is maintained alongside the Contract Analysis system to ensure accuracy and usefulness for all users and developers.

## Streamlit UI (Minimal)

Run the minimal UI to upload a rules file and multiple documents, execute the workflow, and download the master spreadsheet (Granite-only by default):

```bash
# From repo root (ensure .env is set with Granite 3.3)
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
streamlit run ./ui/streamlit_app.py
```

Steps:
- Upload a rules file (CSV/XLSX/YAML)
- Upload reference document (MD/TXT/PDF)
- Upload one or more target documents (MD/TXT/PDF)
- Click Run Workflow
- Download the master spreadsheet at the end (saved also to `data/output/comparisons/contract_analysis_template_master.xlsx`)
