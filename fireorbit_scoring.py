import json

def load_data():
    with open("experiments.json", "r") as f:
        return json.load(f)

def score_experiment(experiment, target_o2, target_pressure_kpa):
    score = 0.0
    max_possible = 0.0
    reasons = []

    # 1. Oxygen Scoring (Weight: 60)
    exp_o2 = experiment.get('oxygen_pct')
    if exp_o2 is not None:
        o2_diff = abs(exp_o2 - target_o2)
        # Linear decay: max score at 0 diff, drops to 0 if diff > 20%
        o2_score = max(0, 1 - (o2_diff / 20.0)) * 60 
        score += o2_score
        max_possible += 60
        
        if o2_diff <= 2.0:
            reasons.append(f"closely matches target oxygen ({exp_o2}% O₂)")
        else:
            reasons.append(f"tested at {exp_o2}% O₂ rather than {target_o2}%")

    # 2. Pressure Scoring (Weight: 40)
    exp_pressure = experiment.get('pressure_kpa')
    if exp_pressure is not None:
        p_diff = abs(exp_pressure - target_pressure_kpa)
        # Linear decay: drops to 0 if diff > 50 kPa
        p_score = max(0, 1 - (p_diff / 50.0)) * 40
        score += p_score
        max_possible += 40
        
        if p_diff <= 10.0:
            reasons.append(f"aligns with pressure constraints ({exp_pressure} kPa)")
        else:
            reasons.append(f"pressure differs ({exp_pressure} vs target {target_pressure_kpa} kPa)")

    # Final Score Normalization (out of 100)
    final_score = (score / max_possible * 100) if max_possible > 0 else 0
    
    # Format the explanation text
    if not reasons:
        explanation = "No matching variables available for comparison."
    else:
        explanation = "Experiment " + " and ".join(reasons) + "."

    return round(final_score, 1), explanation

if __name__ == "__main__":
    experiments = load_data()
    
    # Test Scenario: Moon Base (26.5% O2, 70.3 kPa) as requested by your team
    print("--- MOON BASE SCENARIO TEST ---")
    
    indices_to_test = [0, 100, 300, 600, 1000, 1400]    
    for idx in indices_to_test:
        if idx < len(experiments):
            exp = experiments[idx]
            score, explanation = score_experiment(exp, target_o2=26.5, target_pressure_kpa=70.3)
            print(f"[{exp['id']}] O₂: {exp.get('oxygen_pct')}% | Pressure: {exp.get('pressure_kpa')} kPa → Score: {score}/100 | {explanation}")