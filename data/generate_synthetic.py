import os
import json
import csv
import random
import datetime
import string

random.seed(42)

def random_string(length, prefix="", chars=string.ascii_letters + string.digits):
    return prefix + ''.join(random.choices(chars, k=length))

def random_id(prefix, length=14):
    return prefix + ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def random_date(start_date, end_date):
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    return start_date + datetime.timedelta(days=random_number_of_days, seconds=random.randrange(86400))

NAMES = ["Sharma Electronics", "Patel Textiles", "Gupta Traders", "Reddy Solutions", "Joshi Enterprises", "Singh Motors", "Nair Imports", "Desai Foods", "Rao Consulting", "Kumar Garments"]
PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"]

def generate_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    synth_dir = os.path.join(base_dir, "synthetic")
    os.makedirs(synth_dir, exist_ok=True)
    
    oms_orders = []
    gateway_payments = []
    gateway_refunds = []
    settlement_recon = []
    bank_statement = []
    ground_truth = {
        "metadata": {
            "generated_at": datetime.datetime.now().isoformat(),
            "total_records": 120,
            "matchable_records": 100,
            "exception_records": 20
        },
        "matches": [],
        "exceptions": []
    }

    start_date = datetime.datetime(2024, 6, 1)
    end_date = datetime.datetime(2024, 7, 31)

    running_bank_balance = 100000.0  # In rupees
    
    # 50 clean_exact (amount exact in bank, no fees, immediate settlement)
    # 15 fee_adjusted (standard 2% fee + 18% GST)
    # 10 date_shifted (settled T+1 to T+3)
    # 8 description_garbled 
    # 7 partial_batch (grouped into settlements)
    # 10 refund
    # 5 missing_bank_entry
    # 3 duplicate_payment
    # 4 amount_discrepancy
    # 3 ghost_refund
    # 3 dispute_adjustment
    # 2 orphaned_record

    config = [
        {"cat": "clean_exact", "count": 50},
        {"cat": "fee_adjusted", "count": 15},
        {"cat": "date_shifted", "count": 10},
        {"cat": "description_garbled", "count": 8},
        {"cat": "partial_batch", "count": 7},
        {"cat": "refund", "count": 10},
        {"cat": "missing_bank_entry", "count": 5},
        {"cat": "duplicate_payment", "count": 3},
        {"cat": "amount_discrepancy", "count": 4},
        {"cat": "ghost_refund", "count": 3},
        {"cat": "dispute_adjustment", "count": 3},
        {"cat": "orphaned_record", "count": 2},
    ]

    order_counter = 1
    
    # We will build transactions and then sort bank statements chronologically to calculate running balance.
    bank_entries_unsorted = []
    
    for category in config:
        cat = category["cat"]
        count = category["count"]
        
        if cat == "partial_batch":
            # Group into 3 settlements: sizes 3, 2, 2
            batches = [3, 2, 2]
            for b_size in batches:
                setl_id = random_id("setl_")
                utr = random_string(14, "UTIB", string.digits)
                settled_at = int(random_date(start_date, end_date).timestamp())
                total_credit_paise = 0
                
                for _ in range(b_size):
                    # OMS
                    ord_ref = f"ORD-2024-{order_counter:04d}"
                    order_counter += 1
                    amount = random.randint(200, 50000) * 100
                    created_date = datetime.datetime.fromtimestamp(settled_at - 86400)
                    
                    oms_orders.append({
                        "order_ref": ord_ref,
                        "invoice_id": f"INV-{random.randint(1000, 9999)}",
                        "customer_name": random.choice(NAMES),
                        "customer_email": f"cust{random.randint(1,1000)}@example.com",
                        "amount": amount,
                        "currency": "INR",
                        "status": "completed",
                        "payment_method": random.choice(PAYMENT_METHODS),
                        "created_at": created_date.isoformat(),
                        "notes": ""
                    })
                    
                    pay_id = random_id("pay_")
                    fee = int(amount * 0.02)
                    tax = int(fee * 0.18)
                    credit = amount - fee - tax
                    total_credit_paise += credit
                    
                    gateway_payments.append({
                        "id": pay_id,
                        "entity": "payment",
                        "amount": amount,
                        "currency": "INR",
                        "status": "captured",
                        "order_id": random_id("order_"),
                        "receipt": ord_ref,
                        "method": random.choice(PAYMENT_METHODS),
                        "fee": fee,
                        "tax": tax,
                        "email": f"cust{random.randint(1,1000)}@example.com",
                        "contact": f"9{random.randint(100000000, 999999999)}",
                        "description": "Partial payment",
                        "acquirer_data": {"rrn": random_string(10, chars=string.digits), "auth_code": random_string(6, chars=string.digits)},
                        "created_at": int(created_date.timestamp())
                    })
                    
                    settlement_recon.append({
                        "entity_id": pay_id,
                        "type": "payment",
                        "amount": amount,
                        "currency": "INR",
                        "fee": fee,
                        "tax": tax,
                        "credit": credit,
                        "debit": 0,
                        "settlement_id": setl_id,
                        "utr": utr,
                        "settled_at": settled_at,
                        "created_at": int(created_date.timestamp()),
                        "on_hold": False,
                        "settled": True
                    })
                    
                    ground_truth["matches"].append({
                        "oms_order_ref": ord_ref,
                        "gateway_payment_id": pay_id,
                        "recon_entity_id": pay_id,
                        "bank_utr": utr,
                        "settlement_id": setl_id,
                        "match_category": "partial_batch"
                    })
                    
                bank_entries_unsorted.append({
                    "date": datetime.datetime.fromtimestamp(settled_at),
                    "description": f"NEFT-{utr}-RAZORPAY-SETL",
                    "credit": round(total_credit_paise / 100, 2),
                    "debit": 0.0,
                    "reference": utr
                })
            continue

        for i in range(count):
            amount = random.randint(200, 50000) * 100
            ord_ref = f"ORD-2024-{order_counter:04d}"
            order_counter += 1
            
            created_dt = random_date(start_date, end_date)
            created_ts = int(created_dt.timestamp())
            settled_ts = created_ts + 86400  # Default T+1
            
            pay_id = random_id("pay_")
            setl_id = random_id("setl_")
            utr = random_string(14, "UTIB", string.digits)
            
            fee = int(amount * 0.02)
            tax = int(fee * 0.18)
            credit = amount - fee - tax
            
            if cat == "clean_exact":
                fee = 0
                tax = 0
                credit = amount
            elif cat == "date_shifted":
                settled_ts = created_ts + (random.randint(2, 4) * 86400)
            
            bank_desc = f"NEFT-{utr}-RAZORPAY"
            if cat == "description_garbled":
                bank_desc = f"IMPS/RZP/SETL/{utr[4:10]}..." # Garbled UTR

            oms_status = "refunded" if cat == "refund" else "completed"
            gw_status = "captured"
            recon_credit = credit
            recon_debit = 0
            recon_amt = amount
            
            if cat == "amount_discrepancy":
                # OMS amount different from gateway
                amount_oms = amount + 500
                oms_orders.append({
                    "order_ref": ord_ref,
                    "invoice_id": f"INV-{random.randint(1000, 9999)}",
                    "customer_name": random.choice(NAMES),
                    "customer_email": "test@example.com",
                    "amount": amount_oms,
                    "currency": "INR",
                    "status": oms_status,
                    "payment_method": random.choice(PAYMENT_METHODS),
                    "created_at": created_dt.isoformat(),
                    "notes": "Discrepancy"
                })
            elif cat not in ["ghost_refund", "orphaned_record"]:
                oms_orders.append({
                    "order_ref": ord_ref,
                    "invoice_id": f"INV-{random.randint(1000, 9999)}",
                    "customer_name": random.choice(NAMES),
                    "customer_email": "test@example.com",
                    "amount": amount,
                    "currency": "INR",
                    "status": oms_status,
                    "payment_method": random.choice(PAYMENT_METHODS),
                    "created_at": created_dt.isoformat(),
                    "notes": ""
                })
                
            gateway_payments.append({
                "id": pay_id,
                "entity": "payment",
                "amount": amount,
                "currency": "INR",
                "status": gw_status,
                "order_id": random_id("order_"),
                "receipt": ord_ref if cat != "ghost_refund" else "",
                "method": random.choice(PAYMENT_METHODS),
                "fee": fee,
                "tax": tax,
                "email": "test@example.com",
                "contact": "9999999999",
                "description": "",
                "acquirer_data": {"rrn": "123456", "auth_code": "000"},
                "created_at": created_ts
            })
                
            if cat == "duplicate_payment":
                gateway_payments.append({
                    "id": pay_id,  # Duplicate
                    "entity": "payment",
                    "amount": amount,
                    "currency": "INR",
                    "status": gw_status,
                    "order_id": random_id("order_"),
                    "receipt": ord_ref,
                    "method": "card",
                    "fee": fee,
                    "tax": tax,
                    "email": "test@example.com",
                    "contact": "9999999999",
                    "description": "Dup",
                    "acquirer_data": {"rrn": "123456", "auth_code": "000"},
                    "created_at": created_ts + 10
                })
            
            recon_type = "payment"
            recon_entity_id = pay_id
            
            if cat in ["refund", "ghost_refund"]:
                rfnd_id = random_id("rfnd_")
                gateway_refunds.append({
                    "id": rfnd_id,
                    "payment_id": pay_id,
                    "amount": amount,
                    "status": "processed",
                    "receipt": ord_ref if cat == "refund" else "",
                    "created_at": created_ts + 3600
                })
                recon_type = "refund"
                recon_entity_id = rfnd_id
                recon_credit = 0
                recon_debit = amount
                recon_amt = amount
                fee = 0
                tax = 0
                
            if cat != "orphaned_record":
                settlement_recon.append({
                    "entity_id": recon_entity_id,
                    "type": recon_type,
                    "amount": recon_amt,
                    "currency": "INR",
                    "fee": fee,
                    "tax": tax,
                    "credit": recon_credit,
                    "debit": recon_debit,
                    "settlement_id": setl_id,
                    "utr": utr,
                    "settled_at": settled_ts,
                    "created_at": created_ts,
                    "on_hold": False,
                    "settled": True
                })
            
            if cat not in ["missing_bank_entry", "orphaned_record"]:
                bank_entries_unsorted.append({
                    "date": datetime.datetime.fromtimestamp(settled_ts),
                    "description": bank_desc,
                    "credit": round(recon_credit / 100, 2),
                    "debit": round(recon_debit / 100, 2),
                    "reference": utr
                })
                
            if cat in ["clean_exact", "fee_adjusted", "date_shifted", "description_garbled", "refund"]:
                ground_truth["matches"].append({
                    "oms_order_ref": ord_ref,
                    "gateway_payment_id": pay_id,
                    "recon_entity_id": recon_entity_id,
                    "bank_utr": utr,
                    "settlement_id": setl_id,
                    "match_category": cat
                })
            else:
                ground_truth["exceptions"].append({
                    "source": "multi",
                    "record_id": pay_id,
                    "exception_category": cat,
                    "description": f"Generated exception of type {cat}"
                })

    # Sort bank entries chronologically and calculate running balance
    bank_entries_unsorted.sort(key=lambda x: x["date"])
    for entry in bank_entries_unsorted:
        running_bank_balance += entry["credit"]
        running_bank_balance -= entry["debit"]
        bank_statement.append({
            "date": entry["date"].strftime("%d/%m/%Y"),
            "description": entry["description"],
            "credit": entry["credit"] if entry["credit"] > 0 else "",
            "debit": entry["debit"] if entry["debit"] > 0 else "",
            "balance": round(running_bank_balance, 2),
            "reference": entry["reference"]
        })

    # Write files
    with open(os.path.join(synth_dir, "oms_orders.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["order_ref", "invoice_id", "customer_name", "customer_email", "amount", "currency", "status", "payment_method", "created_at", "notes"])
        writer.writeheader()
        writer.writerows(oms_orders)

    with open(os.path.join(synth_dir, "gateway_payments.json"), "w") as f:
        json.dump(gateway_payments, f, indent=2)

    with open(os.path.join(synth_dir, "gateway_refunds.json"), "w") as f:
        json.dump(gateway_refunds, f, indent=2)

    with open(os.path.join(synth_dir, "settlement_recon.json"), "w") as f:
        json.dump(settlement_recon, f, indent=2)

    with open(os.path.join(synth_dir, "bank_statement.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "description", "credit", "debit", "balance", "reference"])
        writer.writeheader()
        writer.writerows(bank_statement)

    with open(os.path.join(synth_dir, "ground_truth.json"), "w") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Successfully generated synthetic dataset in {synth_dir}")
    print(f"OMS Orders: {len(oms_orders)}")
    print(f"Gateway Payments: {len(gateway_payments)}")
    print(f"Gateway Refunds: {len(gateway_refunds)}")
    print(f"Settlement Recon: {len(settlement_recon)}")
    print(f"Bank Statement Rows: {len(bank_statement)}")
    print(f"Ground Truth Matches: {len(ground_truth['matches'])}")
    print(f"Ground Truth Exceptions: {len(ground_truth['exceptions'])}")

if __name__ == "__main__":
    generate_data()
