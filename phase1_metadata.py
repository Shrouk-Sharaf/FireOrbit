import os
import re
import json

def parse_isa_tab_metadata(folder_path):
    investigation_metadata = {}
    
    # Loop through all text files in the investigations directory
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.startswith("i_Investigation") and file.endswith(".txt"):
                filepath = os.path.join(root, file)
                
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                
                # Helper function to extract tab-separated values
                def extract_field(field_name, is_comment=False):
                    if is_comment:
                        match = re.search(fr'Comment\[{field_name}\]\t(.*?)\n', text)
                    else:
                        match = re.search(fr'{field_name}\t(.*?)\n', text)
                    return match.group(1).strip() if match else None

                # Extract the core metadata fields defined in the strategy
                psi_id = extract_field("Study Identifier")
                if not psi_id:
                    continue
                    
                metadata = {
                    "psi_id": psi_id,
                    "title": extract_field("Study Title"),
                    "acronym": extract_field("Investigation Acronym", is_comment=True),
                    "objective": extract_field("Objective", is_comment=True),
                    "hypothesis": extract_field("Hypothesis", is_comment=True),
                    "approach": extract_field("Approach", is_comment=True),
                    "research_impacts": extract_field("Research Impacts", is_comment=True),
                    "hardware": extract_field("Experiment Hardware", is_comment=True),
                    "flight_platform": extract_field("Flight Platform", is_comment=True),
                    "sub_research_area": extract_field("SubResearch Area", is_comment=True)
                }
                
                investigation_metadata[psi_id] = metadata
                print(f"Extracted metadata for: {psi_id}")
                
    # Save the output to JSON
    output_file = "phase1_metadata.json"
    with open(output_file, "w", encoding='utf-8') as f:
        json.dump(investigation_metadata, f, indent=4)
        
    print(f"\nPhase 1 Complete. Extracted {len(investigation_metadata)} investigations to {output_file}.")

if __name__ == "__main__":
    parse_isa_tab_metadata("./investigations")