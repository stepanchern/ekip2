import requests, zipfile, io, os, csv, re, time, difflib
from sqlalchemy import create_engine, String, Integer, Float, ForeignKey, select, inspect, text, REAL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, relationship
import math
from rapidfuzz import process, fuzz
from sqlalchemy import func

stores = {
    'Lidl':['lidl', 'лидл'],
    'Kaufland':['kaufland', 'кауфланд', 'кауфленд'],
    'Burlex':['бурлекс', 'burlex', 'burleks'],
    'Metro':['метро', 'metro'],
    'Billa':['билла', 'била', 'billa'],
    'MyMarket':['mymarket', 'my market', 'маймаркет', 'май маркет'],
    'BulMag':['булмаг', 'bulmag']
}

class Base(DeclarativeBase):
    pass
class Category(Base):
    __tablename__ = "categories"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
class Chain(Base):
    __tablename__ = "chains"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
class Store(Base):
    __tablename__ = "stores"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    coords: Mapped[str] = mapped_column(String, nullable=True)
    populated_area: Mapped[str] = mapped_column(String, nullable=True)
    address: Mapped[str] = mapped_column(String, nullable=True)
    chain_id: Mapped[int] = mapped_column(nullable=True) 
class ChainName(Base):
    __tablename__ = "chain_names"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    chain_id: Mapped[int] = mapped_column(nullable=True)
class Unit(Base):
    __tablename__ = "units"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
class Product(Base):
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    quantity: Mapped[float] = mapped_column(REAL, nullable=True)
    price: Mapped[float] = mapped_column(REAL)
    
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    unit_id: Mapped[int|None] = mapped_column(ForeignKey("units.id"), nullable=True)

def show_all_data(engine):
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    with engine.connect() as connection:
        if not table_names:
            print("The database is empty (no tables found).")
            return
        for table in table_names:
            print(f"\n=== TABLE: {table.upper()} ===")
            result = connection.execute(text(f"SELECT * FROM {table}"))
            rows = result.fetchall()
            if not rows:
                print("  (Empty)")
            else:
                print(f"  Columns: {result.keys()}")
                for row in rows:
                    print(f"  {row}")
            print("-" * 30)


# populate db
def create_db():
    engine = create_engine("sqlite:///price_comparison.db", echo=False)
    Base.metadata.create_all(engine)
    return engine
def populate_chains(engine, stores):
    with Session(engine) as session:
        for store_name in stores.keys():
            stmt = select(Chain).where(Chain.name == store_name)
            existing_chain = session.execute(stmt).scalar_one_or_none()
            if not existing_chain:
                session.add(Chain(name=store_name))
        session.commit()
def populate_chain_names(engine, stores_dict):
    with Session(engine) as session:
        for main_chain_name, variations in stores_dict.items():
            stmt = select(Chain).where(Chain.name == main_chain_name)
            main_chain = session.execute(stmt).scalar_one_or_none()
            if not main_chain:
                main_chain = Chain(name=main_chain_name)
                session.add(main_chain)
                session.flush()
            for variant in variations:
                stmt_v = select(ChainName).where(ChainName.name == variant)
                if not session.execute(stmt_v).scalar_one_or_none():
                    session.add(ChainName(name=variant, chain_id=main_chain.id))
        session.commit()
def populate_units(engine):
    target_units = ['L', 'KG', 'бр']
    with Session(engine) as session:
        for unit_name in target_units:
            stmt = select(Unit).where(Unit.name == unit_name)
            if not session.execute(stmt).scalar_one_or_none():
                session.add(Unit(name=unit_name))
        session.commit()
def populate_categories(engine):
    raw_text = """1. Бял хляб от 500 гр. до 1 кг
2. Хляб Добруджа от 500 гр. до 1 кг
3. Ръжен хляб от 400 гр. до 600 гр.
4. Типов хляб от 400 гр. до 600 гр.
5. Точени кори от 400 гр. до 500 гр.
6. Прясно мляко от 2 % до 3.6 % 1 л
7. Кисело мляко от 2 % до 3.6 % в кофички от 370 гр. до 500 гр.
8. Сирене от краве мляко насипно 1 кг
9. Сирене от краве мляко пакетирано от 200 гр. до 1 кг
10. Кашкавал от краве мляко насипно 1 кг
11. Кашкавал от краве мляко пакетирано от 200 гр. до 1 кг
12. Краве масло от 125 гр. до 250 гр.
13. Извара насипна 1 кг
14. Извара пакетирана от 200 гр. до 1 кг
15. Прясно охладено пиле 1 кг (цяло)
16. Пилешко филе, охладено, 1 кг
17. Пилешки бут, цял, охладен 1 кг
18. Прясно свинско месо плешка 1 кг
19. Прясно свинско месо бут 1 кг
20. Прясно свинско месо шол 1 кг
21. Прясно свинско месо врат 1 кг
22. Свинско месо за готвене 1 кг
23. Телешко месо шол 1 кг
24. Телешко месо за готвене 1 кг
25. Мляно месо смес 60/40, насипно за 1 кг
26. Кренвирши, насипни за 1 кг
27. Колбаси пресни от 300 гр. до 1 кг
28. Колбаси сухи (Шпек, Бургас, Деликатесен) от 250 гр. до 1 кг
29. Риба замразена (скумрия, пъстърва, лаврак, ципура) 1 кг
30. Риба охладена (скумрия, пъстърва, лаврак, ципура) 1 кг
31. Яйца размер М от 6 бр. до 10 бр. Подово отглеждане
32. Яйца размер L 6 бр. до 10 бр. Подово отглеждане
33. Боб, пакетиран 1 кг
34. Леща, пакетиран 1 кг
35. Бисерен ориз 1 кг
36. Макарони от 400 гр. до 500 гр.
37. Спагети (№ 3, № 5 и № 10) 500 гр.
38. Бяла захар 1 кг
39. Готварска сол 1 кг
40. Брашно тип 500 1 кг
41. Брашно екстра 1 кг
42. Олио слънчогледово 1 л
43. Зехтин 1л
44. Винен оцет 700 мл.
45. Ябълков оцет 700 мл.
46. Консерви боб, от 400 гр. до 800 гр.
47. Консерви грах, от 400 гр. до 800 гр.
48. Консервирани домати, от 400 гр. до 800 гр.
49. Лютеница, от 400 гр. до 800 гр.
50. Лимони, насипни 1кг
51. Портокали, насипни 1кг
52. Банани 1кг
53. Ябълки, насипни 1кг
54. Домати, червени, насипни 1кг
55. Кромид лук, насипен 1кг
56. Моркови, насипни 1кг
57. Бяло зеле 1кг
58. Краставици, насипни 1кг
59. Зрял чесън 1кг
60. Пресни гъби, насипни 1кг
61. Картофи, насипни 1кг
62. Маслини, насипни 1 кг
63. Каша (млечна, плодова) от 190 гр. до 250 гр.
64. Детско пюре от 190 гр. до 250 гр.
65. Адаптирани млека от 400 гр. до 800 гр.
66. Обикновени бисквити
67. Кроасани от 50 гр. до 110 гр.
68. Баница от 100 гр. до 500 гр.
69. Шоколад, млечен, от 80 гр. до 100 гр.
70. Кафе мляно от 200 гр. до 250 гр.
71. Кафе на зърна 1 кг
72. Чай (билков на пакетчета)
73. Минерална вода, 6 бр. в опаковка по 1,5 л.
74. Светла бира 2 л.
75. Бяло вино бутилирано, произход България 750 мл.
76. Червено вино бутилирано, произход България 750 мл.
77. Ракия, произход България 700 мл.
78. Тютюневи изделия, произход България, кутия, пакет
79. Течен препарат за миене на съдове от 400 мл.
80. Четка за зъби – средна твърдост
81. Паста за зъби, туба от 50 мл. до 125 мл.
82. Шампоан за нормална коса – от 250 мл. до 500 мл.
83. Сапун, твърд
84. Класически мокри кърпи пакет
85. Тоалетна хартия 8 ролки"""
    with Session(engine) as session:
        lines = raw_text.strip().split('\n')
        for line in lines:
            if not line: continue
            parts = line.split('.', 1)
            if len(parts) == 2:
                cat_id = int(parts[0].strip())
                cat_name = parts[1].strip()
                stmt = select(Category).where(Category.id == cat_id)
                existing_cat = session.execute(stmt).scalar_one_or_none()
                if not existing_cat:
                    session.add(Category(id=cat_id, name=cat_name))
        session.commit()
def populate_varna_stores(engine):
    varna_data = [
        {"chain": "Lidl", "address": "ул. „Битоля“ 1А", "coords": "43.214929, 27.915363"},
        {"chain": "Lidl", "address": "бул. „1-ви Май“ 6", "coords": "43.177129, 27.906121"},
        {"chain": "Lidl", "address": "ул. „Мир“ 45", "coords": "43.225026, 27.930514"},
        {"chain": "Lidl", "address": "к.к. Св. Константин и Елена, ул. „45-та\" 27", "coords": "43.231646, 28.005942"},
        {"chain": "Lidl", "address": "бул. „Владислав Варненчик“ 257", "coords": "43.220158, 27.882653"},
        {"chain": "Lidl", "address": "бул. „Сливница“ 176", "coords": "43.226953, 27.888197"},
        {"chain": "Lidl", "address": "бул. „Република“ 62", "coords": "43.236310, 27.881631"},
        {"chain": "Lidl", "address": "бул. „Света Елена“ 14", "coords": "43.245490, 27.857657"},
        {"chain": "Kaufland", "address": "ул. „Девня“ 24", "coords": "43.202323, 27.901336"},
        {"chain": "Kaufland", "address": "ул. „д-р Петър Скорчев“ 2", "coords": "43.222448, 27.939705"},
        {"chain": "Kaufland", "address": "бул. „Христо Смирненски“ 2", "coords": "43.221384, 27.890324"},
        {"chain": "Kaufland", "address": "бул. „Република“ 60", "coords": "43.235455, 27.880848"},
        {"chain": "Kaufland", "address": "бул. „Трети март“ 77", "coords": "43.242023, 27.849658"},
        {"chain": "Billa", "address": "бул. „Владислав Варненчик“ 48, ет. 1", "coords": "43.209377, 27.908974"},
        {"chain": "Billa", "address": "ул. „Академик Андрей Сахаров“ 3", "coords": "43.220698, 27.898737"},
        {"chain": "Billa", "address": "ул. „Подвис“ 25", "coords": "43.227293, 27.918539"},
        {"chain": "Billa", "address": "бул. „Цар Освободител“ 205", "coords": "43.232633, 27.889815"},
        {"chain": "Billa", "address": "бул. „Сливница“ 185", "coords": "43.227024, 27.875910"},
        {"chain": "Billa", "address": "ул. „Ана Феликсова“ 12", "coords": "43.235809, 27.877266"},
        {"chain": "BulMag", "address": "бул. „8-ми Приморски полк“ 115, Uptown ниво 1", "coords": "43.214123, 27.925877"},
        {"chain": "BulMag", "address": "бул. „Чаталджа“ 22", "coords": "43.215958, 27.919539"},
        {"chain": "BulMag", "address": "ул. „Академик Андрей Сахаров“ 2, Grand Mall, ет. -2", "coords": "43.217924, 27.898623"},
        {"chain": "BulMag", "address": "бул. „Константин и Фружин“ 18", "coords": "43.246820, 27.846952"}
    ]
    with Session(engine) as session:
        chains = {c.name: c.id for c in session.execute(select(Chain)).scalars()}
        new_stores = []
        for item in varna_data:
            c_id = chains.get(item["chain"])
            new_stores.append(Store(address=item["address"], populated_area="Варна", coords=item["coords"], chain_id=c_id))
        session.add_all(new_stores)
        session.commit()
# parsing data
def get_coords(address):
    if not address: return None
    address = address.replace("rp.", "гр.").strip(' "')
    if '/' in address and ' - ' in address:
        address = address.split(' - ')[-1].replace('/', ', ')
    elif ' - ' in address:
        address = address.split(' - ')[-1]
    address = re.sub(r'^(Билла|Метро|Kaufland|Кауфланд|BulMag|Булмаг)\s+\d*\s*', '', address, flags=re.I)
    address = re.sub(r'\b\d{4}\b', '', address)
    address = re.sub(r'^[\s\-\,]+', '', address).strip()
    try:
        url = "https://photon.komoot.io/api/"
        params = {"q": f"{address}, Bulgaria", "limit": 1}
        headers = {"User-Agent": "Mozilla/5.0"}
        time.sleep(0.5) 
        r = requests.get(url, params=params, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and data.get('features'):
                lon, lat = data['features'][0]['geometry']['coordinates']
                return f"{lat}, {lon}"
    except: pass
    return None
def parse_product(product_string):
    product_string = product_string.replace('~', '').strip()
    clean_name = product_string
    quantity = None
    unit = 'бр'
    full_match_text = ""
    unit_pattern = r'(КГ|ГР|Г|МЛ|Л|БР|KG|GR|G|ML|L|MЛ|КG|KГ|M)'
    range_pattern = r'(\d+)/(\d+)\s*' + unit_pattern
    multi_pattern = r'(\d+)\s*[xхXХ]\s*(\d+[\.,]?\d*)\s*' + unit_pattern
    std_pattern = r'(\d+[\.,]?\d*)\s*' + unit_pattern + r'\b'
    range_match = re.search(range_pattern, product_string, re.I)
    multi_match = re.search(multi_pattern, product_string, re.I)
    std_match = re.search(std_pattern, product_string, re.I)
    if range_match:
        val1 = float(range_match.group(1)); val2 = float(range_match.group(2))
        quantity = (val1 + val2) / 2
        raw_unit = range_match.group(3).upper()
        full_match_text = range_match.group(0)
    elif multi_match:
        count = float(multi_match.group(1))
        val = float(multi_match.group(2).replace(',', '.'))
        quantity = count * val
        raw_unit = multi_match.group(3).upper()
        full_match_text = multi_match.group(0)
    elif std_match:
        quantity = float(std_match.group(1).replace(',', '.'))
        raw_unit = std_match.group(2).upper()
        full_match_text = std_match.group(0)
    else:
        return clean_name, 1.0, 'бр'
    conversions = {
        'Г': ('KG', 0.001), 'ГР': ('KG', 0.001), 'КГ': ('KG', 1.0), 
        'МЛ': ('L', 0.001), 'Л': ('L', 1.0), 'БР': ('бр', 1.0),
        'G': ('KG', 0.001), 'GR': ('KG', 0.001), 'KG': ('KG', 1.0), 
        'ML': ('L', 0.001), 'L': ('L', 1.0), 'M': ('L', 0.001),
        'MЛ': ('L', 0.001), 'КG': ('KG', 1.0), 'KГ': ('KG', 1.0)
    }
    if raw_unit in conversions:
        unit, multiplier = conversions[raw_unit]
        quantity = round(quantity * multiplier, 3)
    if quantity is not None and quantity <= 0.001:
        quantity = 1.0; unit = 'бр'
    if full_match_text:
        clean_name = product_string.replace(full_match_text, "").strip()
        clean_name = re.sub(r'^[\s\.\-\,]+|[\s\.\-\,]+$', '', clean_name)
    return clean_name, quantity, unit
def normalize_address(addr):
    if not addr: return ""
    addr = addr.lower()
    for char in ['„', '“', '"', '(', ')', ' - ет. -2', ', grand mall, ет. -2', ', uptown ниво 1']:
        addr = addr.replace(char, '')
    for prefix in ['ул.', 'бул.', 'гр.', 'к.к.', 'адрес:', 'bulmag', 'булмаг']:
        addr = addr.replace(prefix, '')
    return " ".join(addr.split())
def process_feed(url, engine):
    with Session(engine) as session:
        chains_map = {cn.name.lower(): cn.chain_id for cn in session.execute(select(ChainName)).scalars()}
        chain_id_to_name = {c.id: c.name for c in session.execute(select(Chain)).scalars()}
        units_map = {u.name: u.id for u in session.execute(select(Unit)).scalars()}

    resp = requests.get(url)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        for filename in z.namelist():
            if not filename.endswith('.csv'): continue
            matched_chain_id = next((cid for name, cid in chains_map.items() if name in filename.lower()), None)
            if not matched_chain_id: continue
            chain_display_name = chain_id_to_name.get(matched_chain_id, "Unknown Chain")

            with z.open(filename) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'))
                with Session(engine) as session:
                    db_stores = session.execute(select(Store).where(Store.chain_id == matched_chain_id)).scalars().all()
                    if not db_stores: continue
                    
                    normalized_db = [(s, normalize_address(s.address)) for s in db_stores]
                    db_addresses_only = [item[1] for item in normalized_db]
                    
                    added_count = 0
                    for row in reader:
                        csv_addr_raw = row.get("Търговски обект", "").strip()
                        csv_addr_clean = normalize_address(csv_addr_raw)
                        
                        match = process.extractOne(csv_addr_clean, db_addresses_only, scorer=fuzz.token_set_ratio)
                        target_store = normalized_db[db_addresses_only.index(match[0])][0] if (match and match[1] > 80) else None

                        if target_store:
                            prod_raw = row.get("Наименование на продукта", "").strip()
                            if not prod_raw: continue
                            p_name, p_qty, p_unit_str = parse_product(prod_raw)
                            
                            try:
                                p_retail = row.get("Цена на дребно")
                                p_promo = row.get("Цена в промоция")
                                def clean_p(v): return float(str(v).replace(',', '.')) if v else 0.0
                                price_val = clean_p(p_promo) if clean_p(p_promo) > 0 else clean_p(p_retail)
                                if price_val <= 0: continue
                                
                                # FIX: Only use category if it's a valid digit, otherwise NULL
                                raw_cat = row.get("Категория")
                                cat_id = int(raw_cat) if (raw_cat and str(raw_cat).isdigit()) else None
                                
                                session.add(Product(
                                    name=p_name, quantity=p_qty, price=price_val, 
                                    category_id=cat_id, store_id=target_store.id, 
                                    unit_id=units_map.get(p_unit_str)
                                ))
                                added_count += 1
                            except: continue
                    session.commit()
                    print(f"Processed {filename}: Imported {added_count} products.")
# ranking
def haversine(coord_str1, coord_str2):
    """Calculates distance in KM between two 'lat, lon' strings."""
    try:
        c1 = [float(x) for x in coord_str1.split(',')]
        c2 = [float(x) for x in coord_str2.split(',')]
        R = 6371.0
        lat1, lon1 = math.radians(c1[0]), math.radians(c1[1])
        lat2, lon2 = math.radians(c2[0]), math.radians(c2[1])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    except:
        return 999.0 # Penalty for invalid coords
def get_store_rankings(engine, shopping_list, user_coords_str):
    with Session(engine) as session:
        all_stores = session.execute(select(Store)).scalars().all()
        chains = {c.id: c.name for c in session.execute(select(Chain)).scalars().all()}
        db_categories = session.execute(select(Category)).all()
        
        # 1. PRE-CALCULATE MARKET AVERAGES
        avg_results = session.query(
            Product.category_id, 
            func.avg(Product.price)
        ).group_by(Product.category_id).all()
        
        category_averages = {cat_id: avg_p for cat_id, avg_p in avg_results if cat_id is not None}

        ranking_data = []
        KM_COST_BGN = 0.5     

        for store in all_stores:
            real_basket_sum = 0.0  
            penalty_sum = 0.0
            found_count = 0
            missing_items = []
            chosen_items_list = [] # <--- Track chosen products here
            
            inventory = session.execute(select(Product).where(Product.store_id == store.id)).scalars().all()
            
            for user_item in shopping_list:
                query = user_item.lower().strip()
                cat_match = process.extractOne(
                    query, 
                    [c[0].name for c in db_categories], 
                    scorer=fuzz.partial_ratio
                )
                
                if not cat_match or cat_match[1] < 70:
                    penalty_sum += 3.00 
                    missing_items.append(user_item)
                    continue

                matched_cat_name = cat_match[0]
                target_cat_id = next(c[0].id for c in db_categories if c[0].name == matched_cat_name)

                items_in_cat = [p for p in inventory if p.category_id == target_cat_id]

                if items_in_cat:
                    cheapest_product = min(
                        items_in_cat, 
                        key=lambda p: (p.price / p.quantity) if (p.quantity and p.quantity > 0) else p.price
                    )
                    
                    real_basket_sum += cheapest_product.price
                    found_count += 1
                    
                    # Store details of the chosen item
                    chosen_items_list.append({
                        "name": cheapest_product.name,
                        "price": round(cheapest_product.price, 2),
                        "requested_as": user_item
                    })
                else:
                    penalty_sum += category_averages.get(target_cat_id, 4.00)
                    missing_items.append(user_item)

            if found_count == 0: continue

            dist = haversine(user_coords_str, store.coords)
            internal_score = real_basket_sum + penalty_sum + (dist * KM_COST_BGN)
            
            ranking_data.append({
                "chain_name": chains.get(store.chain_id, 'Unknown'),
                "address": store.address,
                "coords": store.coords,              # <--- Added
                "chosen_items": chosen_items_list,   # <--- Added
                "real_price": round(real_basket_sum, 2),
                "distance_km": round(dist, 2),
                "missing_count": len(missing_items),
                "internal_score": internal_score
            })

        return sorted(ranking_data, key=lambda x: x["internal_score"])
def print_store_rankings(rankings):
    """
    UI Logic: Prints a scannable table followed by a detailed breakdown 
    of the items chosen for each store.
    """
    if not rankings:
        print("\n[!] No stores found with the requested products.")
        return

    print(f"\n{'='*25} TOP STORES IN VARNA {'='*25}")
    # Main Table Header
    header = f"{'RANK':<5} | {'STORE':<40} | {'PRICE':<10} | {'DIST':<8} | {'MISSING'}"
    print(header)
    print("-" * len(header))
    
    for i, r in enumerate(rankings):
        rank_label = f"#{i+1}"
        full_name = f"{r['chain_name']} ({r['address']})"
        
        price_str = f"{r['real_price']:>6.2f} лв" if r['real_price'] > 0 else "  --    "
        dist_str = f"{r['distance_km']:>5.2f} km"
        
        # 1. Print Main Row
        print(f"{rank_label:<5} | {full_name[:38]:<40} | {price_str:<10} | {dist_str:<8} | {r['missing_count']} items")
        
        # 2. Print Detailed Breakdown (Sub-items)
        if r.get("chosen_items"):
            for item in r["chosen_items"]:
                # Indented receipt-style lines
                item_line = f"      > {item['requested_as'].capitalize()}: {item['name'][:30]} ... {item['price']:.2f} лв"
                print(item_line)
        
        # 3. Print Coordinates (Sub-line)
        if r.get("coords"):
            print(f"      @ Coords: {r['coords']}")
        
        print("-" * len(header)) # Separator between stores
    
    print(f"Sorted by: Price + Travel Friction + Dynamic Penalty\n")
def testing():
    file_path = "price_comparison.db"
    if os.path.exists(file_path): os.remove(file_path)
    engine = create_db()
    populate_chains(engine, stores)
    populate_chain_names(engine, stores)
    populate_units(engine)
    populate_categories(engine)
    populate_varna_stores(engine)
    
    # Use the provided URL
    url = 'https://kolkostruva.bg/opendata_files/2026-01-04.zip'
    process_feed(url, engine)
    
# TEST THE RANKING ENGINE
#testing()

user_pos = "43.2047, 27.9100"
my_list = ["хляб", "мляко", "масло", "захар"]
engine = create_engine(f"sqlite:///price_comparison.db", echo=False)

#show_all_data(engine)
results = get_store_rankings(engine, my_list, user_pos)
print_store_rankings(results)