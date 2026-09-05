with open("data/generate_synthetic.py", "r") as f:
    content = f.read()

content = content.replace('if cat != "orphaned_record":\n                gateway_payments.append({', 'gateway_payments.append({')

# For settlement recon:
old_settlement = """                fee = 0
                tax = 0
                
            settlement_recon.append({"""

new_settlement = """                fee = 0
                tax = 0
                
            if cat != "orphaned_record":
                settlement_recon.append({"""
                
content = content.replace(old_settlement, new_settlement)

# For bank entries:
old_bank = """            if cat != "missing_bank_entry":
                bank_entries_unsorted.append({"""

new_bank = """            if cat not in ["missing_bank_entry", "orphaned_record"]:
                bank_entries_unsorted.append({"""
                
content = content.replace(old_bank, new_bank)

with open("data/generate_synthetic.py", "w") as f:
    f.write(content)
