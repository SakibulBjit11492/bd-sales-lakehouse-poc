"""
Generate a synthetic Bangladesh e-commerce Sales star schema as CSV files.

Tables: DimDate, DimGeography (8 divisions, 64 districts), DimCustomer, DimProduct, DimPromotion,
        FactInternetSales (amounts in BDT)
All names, emails and numbers are randomly generated; no real people or companies.

Usage:
    pip install numpy pandas
    python legacy/generate_sales_data_bd.py --out data                      # 10M fact rows
    python legacy/generate_sales_data_bd.py --fact-rows 100000 --customers 10000 --out data  # quick test
"""
import argparse
import os
import time

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- geography
# Division: (share of customers, [(district, relative weight within division), ...])
DIVISIONS = {
    "Dhaka": (0.42, [("Dhaka", 8), ("Gazipur", 2.5), ("Narayanganj", 2), ("Narsingdi", 1), ("Manikganj", 0.6),
                     ("Munshiganj", 0.7), ("Tangail", 1), ("Kishoreganj", 0.8), ("Faridpur", 0.8),
                     ("Gopalganj", 0.5), ("Madaripur", 0.5), ("Rajbari", 0.4), ("Shariatpur", 0.4)]),
    "Chattogram": (0.20, [("Chattogram", 5), ("Cumilla", 1.8), ("Cox's Bazar", 1), ("Feni", 0.8), ("Noakhali", 1),
                          ("Lakshmipur", 0.6), ("Chandpur", 0.7), ("Brahmanbaria", 0.8), ("Rangamati", 0.3),
                          ("Khagrachhari", 0.3), ("Bandarban", 0.2)]),
    "Rajshahi": (0.08, [("Rajshahi", 3), ("Bogura", 2), ("Pabna", 1.2), ("Sirajganj", 1.1), ("Natore", 0.8),
                        ("Naogaon", 0.9), ("Chapai Nawabganj", 0.7), ("Joypurhat", 0.5)]),
    "Khulna": (0.08, [("Khulna", 3), ("Jashore", 2), ("Satkhira", 0.9), ("Bagerhat", 0.8), ("Kushtia", 1.2),
                      ("Chuadanga", 0.6), ("Meherpur", 0.4), ("Jhenaidah", 0.9), ("Magura", 0.5), ("Narail", 0.4)]),
    "Sylhet": (0.07, [("Sylhet", 4), ("Moulvibazar", 1.2), ("Habiganj", 1), ("Sunamganj", 0.8)]),
    "Rangpur": (0.06, [("Rangpur", 3), ("Dinajpur", 1.8), ("Kurigram", 0.8), ("Gaibandha", 0.9), ("Nilphamari", 0.8),
                       ("Lalmonirhat", 0.6), ("Thakurgaon", 0.7), ("Panchagarh", 0.5)]),
    "Barishal": (0.05, [("Barishal", 3), ("Patuakhali", 1), ("Bhola", 1), ("Pirojpur", 0.8), ("Barguna", 0.6),
                        ("Jhalokati", 0.5)]),
    "Mymensingh": (0.04, [("Mymensingh", 3), ("Jamalpur", 1.2), ("Netrokona", 0.9), ("Sherpur", 0.7)]),
}

# ---------------------------------------------------------------- people
MALE = ["Rahim", "Karim", "Tanvir", "Sakib", "Arif", "Imran", "Rakib", "Fahim", "Nayeem", "Mehedi", "Shuvo",
        "Rafi", "Hasan", "Jahid", "Masud", "Anik", "Sajid", "Rubel", "Shafiq", "Partha", "Sumon", "Rana",
        "Tariq", "Asif", "Nafis", "Arnob", "Zahid", "Shakil", "Mahfuz", "Ripon"]
FEMALE = ["Nusrat", "Farzana", "Sadia", "Tasnim", "Sharmin", "Ayesha", "Mithila", "Sumaiya", "Tahmina", "Nadia",
          "Rumana", "Jannat", "Lamia", "Puja", "Shirin", "Riya", "Afsana", "Mim", "Tania", "Sabrina",
          "Fariha", "Raisa", "Anika", "Maliha", "Shathi", "Bristy", "Nabila", "Ishrat", "Tisha", "Orpa"]
LAST = ["Rahman", "Hossain", "Ahmed", "Islam", "Khan", "Chowdhury", "Uddin", "Sarkar", "Das", "Roy", "Mia",
        "Sheikh", "Talukder", "Bhuiyan", "Mahmud", "Haque", "Kabir", "Alam", "Siddique", "Barua", "Saha",
        "Paul", "Majumder", "Biswas", "Karim", "Hasan", "Molla", "Sikder", "Dey", "Akhand"]
LAST_FEMALE = ["Akter", "Khatun", "Begum", "Sultana", "Jahan", "Parvin"]

# ---------------------------------------------------------------- products (prices in BDT)
CATEGORIES = {  # category: (subcategories with price range, variants, share of products)
    "Electronics": ([("Mobile Phone", 8000, 120000), ("Laptop", 35000, 180000), ("Headphone", 500, 15000),
                     ("Smart Watch", 1500, 30000), ("Power Bank", 800, 4000)],
                    ["Black", "White", "Blue", "Silver", "Gold"], 0.20),
    "Fashion": ([("Saree", 1200, 25000), ("Panjabi", 900, 8000), ("Salwar Kameez", 1000, 9000),
                 ("T-Shirt", 300, 1500), ("Shoes", 800, 7000), ("Lungi", 350, 1500)],
                ["Red", "Maroon", "White", "Navy", "Green", "Cream"], 0.30),
    "Home & Kitchen": ([("Rice Cooker", 1800, 6000), ("Blender", 2000, 8000), ("Ceiling Fan", 2500, 7000),
                        ("Cookware Set", 600, 5000), ("Bedsheet", 700, 4000)],
                       ["Small", "Medium", "Large", "Family Size"], 0.20),
    "Grocery": ([("Rice", 350, 900), ("Soybean Oil", 800, 1100), ("Tea", 150, 600), ("Spice Mix", 80, 500),
                 ("Lentils", 120, 400)],
                ["500g", "1kg", "2kg", "5kg"], 0.20),
    "Beauty & Personal Care": ([("Face Wash", 250, 1500), ("Perfume", 500, 6000), ("Hair Oil", 150, 900),
                                ("Lipstick", 250, 2500)],
                               ["Regular", "Herbal", "Premium"], 0.10),
}

# ---------------------------------------------------------------- calendar (dates approximate, Bangladesh)
EID_FITR = ["2017-06-26", "2018-06-16", "2019-06-05", "2020-05-25", "2021-05-14",
            "2022-05-03", "2023-04-22", "2024-04-11", "2025-03-31", "2026-03-21"]
EID_ADHA = ["2017-09-02", "2018-08-22", "2019-08-12", "2020-08-01", "2021-07-21",
            "2022-07-10", "2023-06-29", "2024-06-17", "2025-06-07", "2026-05-27"]

# PromotionKey order matters: keys 1..10
PROMOTIONS = [  # name, discount
    ("No Discount", 0.00), ("Bulk Buy", 0.03), ("Eid ul-Fitr Offer", 0.15), ("Eid ul-Adha Offer", 0.10),
    ("Pohela Boishakh Offer", 0.12), ("11.11 Mega Sale", 0.20), ("Victory Day Offer", 0.16),
    ("Winter Sale", 0.10), ("New User Offer", 0.10), ("Mobile Wallet Offer", 0.05),
]
EVENT_NAMES = {3: "Eid ul-Fitr season", 4: "Eid ul-Adha season", 5: "Pohela Boishakh",
               6: "11.11 Sale", 7: "Victory Day", 8: "Winter Sale"}
VAT = 0.15


def calendar_events(days):
    """Per day: event code (= PromotionKey of the event, 0 = none) and a sales boost factor."""
    code = np.zeros(len(days), dtype=np.int8)
    boost = np.ones(len(days))

    def mark(start, end, c, b):
        m = (days >= np.datetime64(start)) & (days <= np.datetime64(end))
        code[m] = c
        boost[m] = b

    years = range(int(str(days[0])[:4]) - 1, int(str(days[-1])[:4]) + 1)
    for y in years:  # lower priority first, later marks overwrite
        mark(f"{y}-12-20", f"{y + 1}-01-10", 8, 1.10)
        mark(f"{y}-12-14", f"{y}-12-16", 7, 1.30)
        mark(f"{y}-11-09", f"{y}-11-12", 6, 2.00)
        mark(f"{y}-04-07", f"{y}-04-14", 5, 1.40)
    for d in EID_ADHA:
        e = np.datetime64(d)
        mark(e - np.timedelta64(10, "D"), e - np.timedelta64(1, "D"), 4, 1.50)
    for d in EID_FITR:
        e = np.datetime64(d)
        mark(e - np.timedelta64(20, "D"), e - np.timedelta64(1, "D"), 3, 2.20)
    return code, boost


def to_datekey(d):
    y = d.astype("M8[Y]").astype(np.int64) + 1970
    m = d.astype("M8[M]").astype(np.int64) % 12 + 1
    day = (d - d.astype("M8[M]")).astype(np.int64) + 1
    return (y * 10000 + m * 100 + day).astype(np.int32)


def dim_date(start, end):
    d = pd.date_range(start, end, freq="D")
    code, _ = calendar_events(d.values.astype("M8[D]"))
    return pd.DataFrame({
        "DateKey": d.strftime("%Y%m%d").astype(int), "FullDate": d.strftime("%Y-%m-%d"),
        "Year": d.year, "Quarter": d.quarter, "Month": d.month, "MonthName": d.month_name(),
        "DayOfMonth": d.day, "DayOfWeek": d.dayofweek + 1, "DayName": d.day_name(),
        "IsWeekend": d.dayofweek.isin([4, 5]).astype(int),  # Friday and Saturday
        "EventName": [EVENT_NAMES.get(int(c), "") for c in code],
    })


def dim_geography(base_modified):
    rows, weights = [], []
    for div, (share, districts) in DIVISIONS.items():
        total = sum(w for _, w in districts)
        for name, w in districts:
            rows.append({"District": name, "DivisionName": div, "CountryRegionName": "Bangladesh",
                         "IsDivisionalHQ": int(name == div)})
            weights.append(share * w / total)
    df = pd.DataFrame(rows)
    df.insert(0, "GeographyKey", np.arange(1, len(df) + 1))
    df["ModifiedDate"] = base_modified
    w = np.array(weights)
    return df, w / w.sum()


def dim_customer(rng, n, geo_w, base_modified):
    keys = np.arange(1, n + 1)
    gender = rng.choice(np.array(["M", "F"]), n)
    female = gender == "F"
    first = np.where(female, rng.choice(FEMALE, n), rng.choice(MALE, n))
    last = np.where(female & (rng.random(n) < 0.35), rng.choice(LAST_FEMALE, n), rng.choice(LAST, n))
    birth = np.datetime64("1960-01-01") + rng.integers(0, 365 * 45, n).astype("m8[D]")
    first_s, last_s = pd.Series(first), pd.Series(last)
    return pd.DataFrame({
        "CustomerKey": keys,
        "CustomerAlternateKey": pd.Series(keys).map("BD{:08d}".format),
        "FirstName": first_s, "LastName": last_s, "Gender": gender,
        "BirthDate": pd.Series(birth).dt.strftime("%Y-%m-%d"),
        "EmailAddress": first_s.str.lower() + "." + last_s.str.lower() + pd.Series(keys).astype(str) + "@example.com",
        "CustomerSegment": rng.choice(["Individual", "Small Business", "Corporate"], n, p=[0.85, 0.12, 0.03]),
        "GeographyKey": rng.choice(len(geo_w), n, p=geo_w) + 1,
        "ModifiedDate": base_modified,
    })


def dim_product(rng, n, base_modified):
    cats = list(CATEGORIES)
    shares = np.array([CATEGORIES[c][2] for c in cats])
    rows = []
    for key in range(1, n + 1):
        cat = cats[rng.choice(len(cats), p=shares / shares.sum())]
        subs, variants, _ = CATEGORIES[cat]
        sub, lo, hi = subs[rng.integers(len(subs))]
        variant = variants[rng.integers(len(variants))]
        price = float(round(rng.uniform(lo, hi) / 10) * 10)  # round to 10 Taka
        rows.append({
            "ProductKey": key, "ProductAlternateKey": f"{cat[:2].upper()}-{key:05d}",
            "ProductName": f"{sub} {variant} M{rng.integers(100, 999)}",
            "Category": cat, "Subcategory": sub, "Variant": variant,
            "StandardCost": round(price * float(rng.uniform(0.55, 0.80)), 2), "ListPrice": price,
            "ModifiedDate": base_modified,
        })
    return pd.DataFrame(rows)


def dim_promotion():
    return pd.DataFrame({
        "PromotionKey": np.arange(1, len(PROMOTIONS) + 1),
        "PromotionName": [p[0] for p in PROMOTIONS],
        "DiscountPct": [p[1] for p in PROMOTIONS],
    })


def write_fact(rng, path, n_rows, start, end, n_cust, cust_geo, geo, products, chunk_orders):
    days = np.arange(np.datetime64(start), np.datetime64(end) + np.timedelta64(1, "D"), dtype="M8[D]")
    years = days.astype("M8[Y]").astype(np.int64) + 1970
    months = days.astype("M8[M]").astype(np.int64) % 12 + 1
    dow = (days.astype(np.int64) + 3) % 7  # 0 = Monday, 4 = Friday
    event, boost = calendar_events(days)
    growth = (1 + 0.10 * (years - years.min())) * np.where(days >= np.datetime64("2020-04-01"), 1.35, 1.0)
    season = np.array([1.0, 0.95, 1.0, 1.0, 1.0, 0.95, 0.9, 0.95, 1.0, 1.0, 1.05, 1.1])[months - 1]
    w = growth * season * boost * np.where(dow == 4, 1.10, 1.0)
    w /= w.sum()

    # Orders: 1-4 lines each, trimmed so total lines == n_rows exactly
    lines = rng.choice(np.array([1, 2, 3, 4], dtype=np.int8), n_rows, p=[0.45, 0.30, 0.15, 0.10])
    cs = np.cumsum(lines, dtype=np.int64)
    n_orders = int(np.searchsorted(cs, n_rows)) + 1
    lines = lines[:n_orders]
    lines[-1] -= cs[n_orders - 1] - n_rows

    # Order-level attributes; dates sorted so order numbers increase with time
    order_day = np.sort(rng.choice(len(days), n_orders, p=w)).astype(np.int32)
    order_cust = rng.integers(1, n_cust + 1, n_orders, dtype=np.int32)
    order_secs = rng.integers(9 * 3600, 24 * 3600 - 1, n_orders, dtype=np.int32)

    # Promotions: on event days about half of orders use the event offer
    ev = event[order_day]
    normal = rng.choice(np.array([1, 2, 9, 10], dtype=np.int16), n_orders, p=[0.85, 0.05, 0.04, 0.06])
    order_promo = np.where((ev > 0) & (rng.random(n_orders) < 0.55), ev, normal).astype(np.int16)

    # Payment method: Cash on Delivery shrinks over time, mobile wallets grow (Nagad from 2019)
    t = (years[order_day] - years.min()).astype(float)
    p_cod = np.clip(0.85 - 0.03 * t, 0.50, None)
    p_bkash = 0.08 + 0.02 * t
    p_nagad = np.where(years[order_day] >= 2019, 0.01 + 0.012 * (years[order_day] - 2019), 0.0)
    u = rng.random(n_orders)
    pay_idx = np.select([u < p_cod, u < p_cod + p_bkash, u < p_cod + p_bkash + p_nagad], [0, 1, 2], 3)
    pay_names = np.array(["Cash on Delivery", "bKash", "Nagad", "Card"])

    # Delivery charge: 60 BDT inside Dhaka district, 120 outside; free for orders of 3,000 BDT or more
    dhaka_key = int(geo.loc[geo["District"] == "Dhaka", "GeographyKey"].iloc[0])
    order_inside_dhaka = cust_geo[order_cust - 1] == dhaka_key

    disc_pct = np.array([p[1] for p in PROMOTIONS])
    n_prod = len(products)
    pw = 1.0 / np.arange(1, n_prod + 1) ** 0.8
    pw = rng.permutation(pw / pw.sum())
    list_price = products["ListPrice"].to_numpy()
    std_cost = products["StandardCost"].to_numpy()
    cat_is_grocery = (products["Category"] == "Grocery").to_numpy()

    first_order_no = 100001
    written = 0
    for s in range(0, n_orders, chunk_orders):
        e = min(s + chunk_orders, n_orders)
        L = lines[s:e].astype(np.int64)
        tot = int(L.sum())
        rep = np.repeat(np.arange(e - s), L)
        line_no = np.arange(tot) - np.repeat(np.cumsum(L) - L, L) + 1

        od = days[order_day[s:e]][rep]
        prod = rng.choice(n_prod, tot, p=pw) + 1
        qty = np.where(cat_is_grocery[prod - 1],
                       rng.choice([1, 2, 3, 5], tot, p=[0.5, 0.3, 0.12, 0.08]),
                       rng.choice([1, 2, 3], tot, p=[0.85, 0.12, 0.03]))
        promo = order_promo[s:e][rep]
        unit = list_price[prod - 1]
        cost = std_cost[prod - 1]
        ext = np.round(unit * qty, 2)
        disc = np.round(ext * disc_pct[promo - 1], 2)
        sales = np.round(ext - disc, 2)

        order_total = np.bincount(rep, weights=sales, minlength=e - s)
        charge = np.where(order_inside_dhaka[s:e], 60.0, 120.0)
        charge = np.where(order_total >= 3000, 0.0, charge)
        delivery = np.where(line_no == 1, charge[rep], 0.0)

        df = pd.DataFrame({
            "SalesOrderNumber": "BD-SO" + pd.Series(first_order_no + s + rep).astype(str),
            "SalesOrderLineNumber": line_no,
            "OrderDateKey": to_datekey(od),
            "DueDateKey": to_datekey(od + np.timedelta64(5, "D")),
            "ShipDateKey": to_datekey(od + np.timedelta64(2, "D")),
            "CustomerKey": order_cust[s:e][rep],
            "ProductKey": prod,
            "PromotionKey": promo,
            "PaymentMethod": pay_names[pay_idx[s:e][rep]],
            "OrderQuantity": qty,
            "UnitPrice": unit,
            "ExtendedAmount": ext,
            "DiscountAmount": disc,
            "ProductStandardCost": cost,
            "TotalProductCost": np.round(cost * qty, 2),
            "SalesAmount": sales,
            "TaxAmt": np.round(sales * VAT, 2),
            "DeliveryCharge": delivery,
            "CurrencyCode": "BDT",
            "ModifiedDate": pd.Series(od.astype("M8[s]") + order_secs[s:e][rep].astype("m8[s]"))
                              .dt.strftime("%Y-%m-%d %H:%M:%S"),
        })
        df.to_csv(path, mode="w" if s == 0 else "a", header=(s == 0), index=False, float_format="%.2f")
        written += tot
        print(f"  FactInternetSales: {written:,} / {n_rows:,} rows", flush=True)
    return n_orders


def main():
    ap = argparse.ArgumentParser(description="Generate synthetic Bangladesh Sales star schema CSVs")
    ap.add_argument("--fact-rows", type=int, default=10_000_000)
    ap.add_argument("--customers", type=int, default=500_000)
    ap.add_argument("--products", type=int, default=1_000)
    ap.add_argument("--start", default="2017-01-01", help="first order date")
    ap.add_argument("--end", default="2026-10-31", help="last order date")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--chunk-orders", type=int, default=500_000)
    ap.add_argument("--out", default="synthetic_sales_bd")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    base_modified = f"{a.start} 00:00:00"
    t0 = time.time()

    dim_date("2015-01-01", "2030-12-31").to_csv(f"{a.out}/DimDate.csv", index=False)
    geo, geo_w = dim_geography(base_modified)
    geo.to_csv(f"{a.out}/DimGeography.csv", index=False)
    cust = dim_customer(rng, a.customers, geo_w, base_modified)
    cust.to_csv(f"{a.out}/DimCustomer.csv", index=False)
    products = dim_product(rng, a.products, base_modified)
    products.to_csv(f"{a.out}/DimProduct.csv", index=False)
    dim_promotion().to_csv(f"{a.out}/DimPromotion.csv", index=False)
    print(f"Dimensions written ({time.time() - t0:.1f}s)")

    n_orders = write_fact(rng, f"{a.out}/FactInternetSales.csv", a.fact_rows, a.start, a.end, a.customers,
                          cust["GeographyKey"].to_numpy(), geo, products, a.chunk_orders)
    print(f"Done: {a.fact_rows:,} lines in {n_orders:,} orders -> {a.out}/ ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
