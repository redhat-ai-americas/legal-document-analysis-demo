# Legal Document Analysis Teaching Guide

## Overview

This teaching guide provides comprehensive materials for understanding, demonstrating, and extending the Legal Document Analysis system. The guide is designed for developers, technical teams, and educators who want to learn about LangGraph-based document analysis workflows.

## Guide Structure

```
teaching_guide/
├── README.md                  # This file - overview and navigation
├── 01_system_overview.md      # Architecture and concepts
├── 02_getting_started.md      # Setup and first run
├── 03_core_concepts.md        # LangGraph, critics, state management
├── 04_workflow_walkthrough.md # Detailed node-by-node explanation
├── 05_customization.md        # How to extend and modify
├── 06_troubleshooting.md      # Common issues and solutions
├── exercises/                 # Hands-on learning activities
├── solutions/                 # Exercise solutions
├── demos/                     # Demo scripts and examples
└── assets/                    # Diagrams and supporting materials
```

## Learning Path

### Module 1: Foundation (2-3 hours)
- System architecture overview
- Environment setup
- Running your first analysis
- Understanding outputs

### Module 2: Core Concepts (3-4 hours)
- LangGraph state machines
- Critic validation pattern
- Prompt management system
- Model configuration

### Module 3: Deep Dive (4-5 hours)
- Node-by-node workflow analysis
- Classification system
- Rule evaluation engine
- Citation management

### Module 4: Customization (3-4 hours)
- Adding new nodes
- Creating custom critics
- Extending questionnaires
- Defining new rules

### Module 5: Advanced Topics (2-3 hours)
- Performance optimization
- Error handling strategies
- Deployment considerations
- Integration patterns

## Quick Start

1. **Prerequisites Check**
   ```bash
   python --version  # Should be 3.11+
   git --version
   ```

2. **Environment Setup**
   ```bash
   git clone <repository>
   cd legal-document-analysis
   make venv
   source .venv/bin/activate
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Run Demo**
   ```bash
   python teaching_guide/demos/basic_demo.py
   ```

## Key Learning Objectives

By the end of this guide, you will understand:

1. **Architecture Patterns**
   - State-driven workflows in LangGraph
   - Critic agent validation patterns
   - Separation of concerns in document analysis

2. **Technical Implementation**
   - Node development with BaseNode pattern
   - YAML-based prompt management
   - Multi-model LLM configuration
   - Output file generation and inspection

3. **Practical Skills**
   - Running contract analysis workflows
   - Interpreting classification results
   - Evaluating rule compliance
   - Debugging workflow issues

4. **Extension Capabilities**
   - Adding custom business rules
   - Creating new questionnaire sections
   - Implementing additional critics
   - Integrating with external systems

## Teaching Approach

### For Instructors

This guide uses a progressive disclosure approach:
1. Start with high-level concepts
2. Gradually introduce technical details
3. Reinforce with hands-on exercises
4. Provide real-world examples

### For Self-Study

- Follow modules in order for best results
- Complete exercises before checking solutions
- Run demos to see concepts in action
- Experiment with modifications

## Support Resources

- **Sample Documents**: Located in `sample_documents/`
- **Test Suite**: Run `make test` to verify setup
- **Logs**: Check `logs/runs/` for detailed execution logs
- **Output Examples**: See `data/output/` for sample results

## Common Use Cases

### 1. Contract Review
Analyze vendor contracts against standard templates to identify deviations and risks.

### 2. Compliance Checking
Evaluate documents against regulatory requirements and internal policies.

### 3. Due Diligence
Systematically review legal documents during M&A or investment processes.

### 4. Template Validation
Ensure contract templates meet organizational standards and requirements.

## Next Steps

1. Start with [01_system_overview.md](01_system_overview.md) for architectural understanding
2. Follow [02_getting_started.md](02_getting_started.md) to set up your environment
3. Work through exercises in the `exercises/` directory
4. Explore demos for practical examples

## Feedback

This teaching guide is continuously improved. Please report issues or suggestions through the project's issue tracker.