# Comprehensive prompts for Gemini AI analysis

CLAIM_ANALYSIS_PROMPT = """
As a senior marine insurance claims analyst, thoroughly analyze the provided insurance claim document. 

STRUCTURE YOUR ANALYSIS AS JSON WITH THESE SECTIONS:

{
  "claim_number": "Extracted claim number",
  "insured_party": "Name of insured party/organization",
  "policy_number": "Extracted policy number if available",
  "loss_date": "Date of loss incident (YYYY-MM-DD format)",
  "loss_location": "Geographic location of loss",
  "claim_amount": "Numeric claim amount",
  "currency": "Currency of claim amount",
  "loss_description": "Detailed description of the loss incident",
  "vessel_details": {
    "vessel_name": "Name of vessel if marine claim",
    "imo_number": "IMO number if available",
    "type_of_vessel": "Type of vessel",
    "year_built": "Year vessel was built"
  },
  "cargo_details": {
    "cargo_type": "Type of cargo involved",
    "cargo_value": "Value of cargo",
    "origin": "Origin port",
    "destination": "Destination port"
  },
  "coverage_analysis": {
    "policy_coverage": "Assessment of policy coverage applicability",
    "exclusions_noted": "List of potential policy exclusions",
    "limits_available": "Insurance limits information"
  },
  "liability_assessment": {
    "liable_parties": "Parties potentially liable",
    "degree_of_fault": "Assessment of fault percentage",
    "contributing_factors": "Factors contributing to loss"
  },
  "damage_assessment": {
    "extent_of_damage": "Description of damage extent",
    "repair_estimates": "Repair cost estimates if available",
    "business_interruption": "Business impact assessment"
  },
  "documentation_review": {
    "supporting_docs": "List of supporting documents mentioned",
    "documentation_gaps": "Missing documentation identified",
    "verification_required": "Items needing verification"
  },
  "key_findings": ["List of 3-5 most important findings"],
  "recommendations": ["List of 3-5 actionable recommendations"],
  "confidence_score": 0.85,
  "analysis_summary": "Brief overall assessment summary"
}

Focus on marine insurance specifics: hull damage, cargo claims, liability issues, salvage operations, general average, etc.
"""

FRAUD_DETECTION_PROMPT = """
As a fraud detection specialist in marine insurance, analyze this claim for potential fraud indicators.

STRUCTURE YOUR FRAUD ANALYSIS AS JSON:

{
  "fraud_indicators": [
    "List of specific fraud indicators found",
    "Each indicator with brief explanation"
  ],
  "red_flags": [
    "List of red flags requiring investigation",
    "Include severity level for each"
  ],
  "anomalies_detected": {
    "temporal_anomalies": "Unusual timing patterns",
    "financial_anomalies": "Suspicious financial patterns", 
    "document_anomalies": "Document inconsistencies",
    "behavioral_anomalies": "Unusual claimant behavior"
  },
  "fraud_patterns": [
    "Known fraud patterns matched",
    "With confidence levels"
  ],
  "confidence": 0.75,
  "risk_level": "LOW/MEDIUM/HIGH",
  "recommendations": [
    "Specific investigation steps",
    "Verification requirements",
    "Additional documentation needed"
  ]
}

Look for patterns like: inflated values, duplicate claims, staged incidents, document tampering, suspicious timing, etc.
"""

DUPLICATE_DETECTION_PROMPT = """
As a claims processing expert, determine if the current claim is a duplicate or variation of previously processed claims.

STRUCTURE YOUR DUPLICATE ANALYSIS AS JSON:

{
  "is_duplicate": true/false,
  "confidence": 0.85,
  "matching_claims": [
    {
      "claim_id": "ID of matching claim",
      "match_type": "exact/similar/variant",
      "similarity_score": 0.95,
      "matching_elements": ["claim_number", "amount", "dates", etc.],
      "differences": ["minor variations found"]
    }
  ],
  "match_reasoning": "Explanation of why claims are considered duplicates",
  "recommendation": "How to handle the duplicate finding"
}

Compare: claim numbers, insured parties, loss details, amounts, dates, and descriptive elements.
"""

EXCLUSION_CHECK_PROMPT = """
As a marine insurance policy expert, check this claim against standard policy exclusions.

STRUCTURE YOUR EXCLUSION ANALYSIS AS JSON:

{
  "applicable_exclusions": [
    {
      "exclusion_type": "Type of exclusion",
      "policy_reference": "Relevant policy section",
      "applicability": "Full/Partial/Not Applicable",
      "reasoning": "Explanation of applicability"
    }
  ],
  "coverage_gaps": "Areas where coverage may not apply",
  "recommendations": "How to address exclusion issues"
}

Focus on marine-specific exclusions: wear and tear, inherent vice, war risks, piracy, etc.
"""

TREATY_VALIDATION_PROMPT = """
As a reinsurance treaty expert, validate this claim against applicable reinsurance treaties.

STRUCTURE YOUR TREATY ANALYSIS AS JSON:

{
  "treaty_applicability": {
    "treaty_identification": "Which treaties apply",
    "layer_application": "How claim fits treaty layers",
    "retention_levels": "Applicable retention amounts"
  },
  "validation_issues": [
    "Any treaty compliance issues found",
    "With severity levels"
  ],
  "recovery_potential": "Assessment of reinsurance recovery",
  "treaty_recommendations": "Steps for treaty compliance"
}
"""