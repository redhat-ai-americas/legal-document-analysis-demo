#!/usr/bin/env python3
"""
Demo: Template Excel Output

Shows the new template Excel format that matches the provided template structure.
This creates Excel outputs that align with due diligence review templates.
"""

import os
from datetime import datetime
from utils.template_excel_writer import create_template_excel, map_questionnaire_to_template_row

def create_sample_analysis_data():
    """Create sample analysis data to demonstrate the template format."""
    return {
        'executive_summary': {
            'document_name': 'Software Service Agreement - TechCorp.pdf',
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'overall_recommendation': 'HIGH CAUTION - Comprehensive legal review required before signing',
            'risk_level': 'HIGH',
            'quality_grade': 'B+ (82%)',
            'key_statistics': {
                'total_red_flags': 7,
                'critical_issues': 2,
                'high_risk_issues': 3,
                'analysis_confidence': '82%'
            }
        },
        'document_information': {
            'document_name': {'answer': 'Software Service Agreement - TechCorp.pdf'},
            'reviewer_name': {'answer': 'AI Analysis System'},
            'target_company_name': {'answer': 'TechCorp Solutions Inc.'},
            'counterparty_name': {'answer': 'Enterprise Software Systems LLC'},
            'datasite_location': {'answer': '/contracts/due_diligence/folder_A'},
            'contract_start_date': {'answer': '2024-01-01'},
            'agreement_type': {'answer': 'Master Software Service Agreement'},
            'based_on_standard_terms': {'answer': 'Third-Party Paper'}
        },
        'key_clause_analysis': {
            'source_code_access': {
                'answer': 'Yes, counterparty has rights to access source code through escrow arrangement. Release triggers include bankruptcy, failure to provide support for 90+ days, or breach of maintenance obligations. Usage rights post-release include internal use, modification, and redistribution within customer organization.'
            },
            'exclusivity_non_competes': {
                'answer': 'No explicit exclusivity provisions found. Contract does not impose non-compete restrictions on the seller.'
            },
            'forced_pricing_adjustments': {
                'answer': 'Yes, contains Most Favored Customer clause in Section 12.4. Customer entitled to pricing no less favorable than pricing offered to any other customer for substantially similar services.'
            },
            'ip_rights': {
                'answer': 'Mixed IP ownership structure. Customer retains ownership of their data and pre-existing IP. Work product created specifically for customer becomes customer-owned. Platform IP remains with vendor. Some concerns about scope of license grants.'
            },
            'limitation_of_liability': {
                'answer': 'Liability cap set at 12 months of fees paid. However, no cap on direct damages and limited waiver for consequential damages. Carve-outs include IP infringement, data breaches, and willful misconduct.'
            },
            'assignment_coc': {
                'answer': 'Assignment requires written consent. Change of Control clause triggered by acquisition of 50% or more ownership. Acquirer must meet financial and technical qualification criteria.'
            },
            'indemnity': {
                'answer': 'Mutual indemnification with customer providing broader coverage. Customer indemnifies for data content, regulatory compliance, and third-party integrations. Vendor indemnifies for IP infringement and platform security breaches.'
            }
        },
        'gaps_and_comments': {
            'knowledge_gaps': {'answer': 'Missing: data retention policies, disaster recovery SLAs, specific security certifications. Need clarification on international data transfer restrictions.'},
            'internal_comments': {'answer': 'High-risk contract requiring legal review. Source code escrow and MFC provisions are concerning. Liability caps may be insufficient given deal size.'}
        },
        'risk_assessment': {
            'overall_risk_assessment': {
                'document_risk_level': 'HIGH',
                'average_risk_score': 7.2,
                'maximum_risk_score': 9.5
            },
            'red_flag_summary': {
                'total_red_flags': 7,
                'severity_breakdown': {'Critical': 2, 'High': 3, 'Medium': 2, 'Low': 0}
            }
        },
        'quality_metrics': {
            'quality_grade': 'B+',
            'overall_quality_score': 82,
            'manual_review_required': True
        }
    }

def main():
    print("🔷 Template Excel Demo")
    print("="*50)
    
    # Create sample data
    print("📋 Creating sample contract analysis data...")
    analysis_data = create_sample_analysis_data()
    
    # Demo paths
    target_doc = ""
    reference_doc = ""
    
    # Test template mapping
    print("\n📊 Testin template mapping...")
    try:
        row_data = map_questionnaire_to_template_row(analysis_data, target_doc, reference_doc)
        print("✅ Template mapping successful!")
        
        print("\n📋 Key Template Fields:")
        template_fields = [
            "Reviewer Name", "Target Name", "Document Name", "Contract Start Date",
            "Type of Agreement", "Source Code Y/N", "Source Code Details",
            "Exclusivity Y/N", "Exclusivity Details", "Pricing Y/N", "Pricing Details",
            "IP Y/N", "IP Details", "Liability Y/N", "Liability Details",
            "Assignment Y/N", "Assignment Details", "Other Terms", "Comments"
        ]
        
        for field in template_fields[:10]:  # Show first 10 fields
            value = row_data.get(field, 'N/A')
            if len(str(value)) > 60:
                value = str(value)[:57] + "..."
            print(f"  • {field}: {value}")
        
        print(f"  ... and {len(template_fields)-10} more fields")
        
    except Exception as e:
        print(f"❌ Template mapping failed: {e}")
        return
    
    # Create template Excel file
    print("\n📊 Creating template Excel file...")
    output_path = "demo_template_output.yaml"
    
    try:
        excel_path = create_template_excel(analysis_data, output_path, target_doc, reference_doc)
        if excel_path:
            print(f"✅ template Excel created: {excel_path}")
            
            # Check file size
            if os.path.exists(excel_path):
                file_size = os.path.getsize(excel_path)
                print(f"📁 File size: {file_size:,} bytes")
                
                print("\n🎯 Template Features:")
                print("  • Y/N columns with conditional formatting")
                print("  • Detailed sections for each risk area")
                print("  • Professional formatting with headers")
                print("  • Auto-sized columns for readability")
                print("  • Risk level color coding")
                
                print("\n📂 Open the file to see the template format:")
                print(f"   {excel_path}")
                
        else:
            print("❌ Excel creation failed")
            
    except Exception as e:
        print(f"❌ Excel creation error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n🔷 Demo complete! The new system supports:")
    print("  ✅ template Excel format (Y/N + Details columns)")
    print("  ✅ Generic Excel format (Question/Answer rows)")
    print("  ✅ Markdown reports for human review")
    print("  ✅ YAML data for detailed analysis")
    print("  ✅ Structured output organization")
    print("  ✅ Master comparison Excel across documents")

if __name__ == "__main__":
    main() 