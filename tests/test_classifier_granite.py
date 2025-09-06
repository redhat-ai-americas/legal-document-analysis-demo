import yaml
import json
from utils.granite_client import GraniteClient

def load_prompt(prompt_file: str) -> dict:
    """Load a prompt template from a YAML file."""
    with open(prompt_file, 'r') as f:
        return yaml.safe_load(f)

def format_prompt(template: dict, document: str, classes: str) -> str:
    """Format the prompt template with variables."""
    return template['template'].format(
        document=document,
        classes=classes
    )

def main():
    # Initialize the Granite client
    client = GraniteClient()
    
    # Load the classifier prompt
    prompt_template = load_prompt('prompts/classifier.yaml')
    
    # Test document and classes
    test_document = """
    The Supplier shall maintain comprehensive insurance coverage with policy limits of 
    not less than $5,000,000 per occurrence for bodily injury and property damage.
    """
    
    test_classes = """
    insurance_requirement:
        definition: Clauses that specify insurance requirements for parties
        examples:
        - "Vendor shall maintain general liability insurance of at least $1M"
        - "Contractor must carry workers compensation insurance"
        
    limitation_of_liability:
        definition: Clauses that limit the liability of one or both parties
        examples:
        - "In no event shall liability exceed the amount paid"
        - "Neither party shall be liable for indirect damages"
    """
    
    # Format the prompt
    formatted_prompt = format_prompt(prompt_template, test_document, test_classes)
    
    # Make the API call with metadata
    response = client._make_request({
        "model": client.model_name,
        "messages": [{"role": "user", "content": formatted_prompt}],
        "max_tokens": 512,
        "temperature": 0.0,
        "logprobs": True
    })
    
    # Pretty print the entire API response
    print("\nFull API Response:")
    print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    main() 