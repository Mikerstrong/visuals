import json
import random
from datetime import datetime, date

def generate_sample_data():
    groups = ["GroupA", "GroupB", "GroupC", "Parts"]
    
    # Part name prefixes for variety
    part_prefixes = {
        "GroupA": ["Widget", "Component", "Assembly", "Module", "Unit"],
        "GroupB": ["Sensor", "Controller", "Interface", "Adapter", "Switch"], 
        "GroupC": ["Circuit", "Board", "Chip", "Processor", "Memory"],
        "Parts": ["Bolt", "Screw", "Washer", "Gasket", "Spring"]
    }
    
    # Amount ranges per group (based on budgets)
    amount_ranges = {
        "GroupA": (500, 5000),    # Budget: 50,000
        "GroupB": (400, 4000),    # Budget: 40,000
        "GroupC": (550, 5500),    # Budget: 55,500
        "Parts": (1000, 8000)     # Budget: 290,000
    }
    
    data = []
    record_id = 1
    
    # Generate 75 records for each month
    for month, year in [(11, 2025), (12, 2025)]:  # November and December 2025
        # Days in month
        if month == 11:
            max_day = 30  # Full previous month
        else:  # December - only up to today
            max_day = 12  # Current date is December 12, 2025
            
        for _ in range(75):  # 75 records per month
            group = random.choice(groups)
            prefix = random.choice(part_prefixes[group])
            part_name = f"{prefix}-{record_id:04d}"
            
            # Random day in the month - for current month, only up to today
            if month == 12:  # Current month
                day = random.randint(1, max_day)  # Only up to today (Dec 12)
            else:  # Previous month
                day = random.randint(1, min(max_day, 28))  # Full previous month
            date_str = f"{year}-{month:02d}-{day:02d}"
            
            # Random amount within group range
            min_amt, max_amt = amount_ranges[group]
            amount = round(random.uniform(min_amt, max_amt), 2)
            
            data.append({
                "Part Name": part_name,
                "Group Name": group,
                "Date": date_str,
                "Amount": amount
            })
            
            record_id += 1
    
    # Sort by date and group for better organization
    data.sort(key=lambda x: (x["Date"], x["Group Name"]))
    
    return data

if __name__ == "__main__":
    sample_data = generate_sample_data()
    
    with open("sample.json", "w", encoding="utf-8") as f:
        json.dump(sample_data, f, indent=2)
    
    print(f"Generated {len(sample_data)} sample records")
    
    # Show distribution
    from collections import Counter
    group_counts = Counter(item["Group Name"] for item in sample_data)
    month_counts = Counter(item["Date"][:7] for item in sample_data)  # YYYY-MM
    
    print("\nGroup distribution:")
    for group, count in group_counts.items():
        print(f"  {group}: {count}")
    
    print("\nMonth distribution:")
    for month, count in month_counts.items():
        print(f"  {month}: {count}")