import requests, zipfile, io, os, csv, re, time
from sqlalchemy import create_engine, String, Integer, Float, ForeignKey, select, inspect, text, REAL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, relationship

stores = {
    'Lidl':['lidl', 'лидл'],
    'Kaufland':['kaufland', 'кауфланд', 'кауфленд'],
    'Burlex':['бурлекс', 'burlex', 'burleks'],
    'Metro':['метро', 'metro'],
    'Billa':['билла', 'била', 'billa'],
    'MyMarket':['mymarket', 'my market', 'маймаркет', 'май маркет']
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
    # Note: In a real ORM setup, you would usually link this to Chain.id using ForeignKey
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
    
    # Foreign Keys are defined here
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    unit_id: Mapped[int|None] = mapped_column(ForeignKey("units.id"), nullable=True)



def show_all_data(engine):
    # 1. Create an "inspector" to look at the database structure
    inspector = inspect(engine)
    
    # 2. Get a list of all table names (e.g., ['brands', 'products', ...])
    table_names = inspector.get_table_names()
    
    # 3. Connect to the database to read data
    with engine.connect() as connection:
        
        if not table_names:
            print("The database is empty (no tables found).")
            return

        for table in table_names:
            print(f"\n=== TABLE: {table.upper()} ===")
            
            # Select everything from this table
            # We use text() because we are passing a string SQL command
            result = connection.execute(text(f"SELECT * FROM {table}"))
            
            # Get the rows
            rows = result.fetchall()
            
            if not rows:
                print("  (Empty)")
            else:
                # Print the column headers (keys)
                print(f"  Columns: {result.keys()}")
                # Print each row
                for row in rows:
                    print(f"  {row}")
            
            print("-" * 30) # A separator line
def create_db():
    # echo=True prints the SQL it writes for you (great for learning)
    engine = create_engine("sqlite:///price_comparison.db", echo=False)
    
    # This magic line looks at all your classes above and runs "CREATE TABLE"
    Base.metadata.create_all(engine)
    
    return engine
def populate_chains(engine, stores):
    with Session(engine) as session:
        for store_name in stores.keys():
            # 1. Check if a chain with this name already exists
            stmt = select(Chain).where(Chain.name == store_name)
            existing_chain = session.execute(stmt).scalar_one_or_none()
            
            # 2. Only add if it doesn't exist
            if not existing_chain:
                session.add(Chain(name=store_name))
                print(f"Added new chain: {store_name}")
            else:
                print(f"Chain '{store_name}' already exists, skipping...")
        
        # Commit once after the loop for better performance
        session.commit()
def populate_chain_names(engine, stores_dict):
    with Session(engine) as session:
        for main_chain_name, variations in stores_dict.items():
            # Check if Main Chain exists
            stmt = select(Chain).where(Chain.name == main_chain_name)
            main_chain = session.execute(stmt).scalar_one_or_none()
            
            if not main_chain:
                main_chain = Chain(name=main_chain_name)
                session.add(main_chain)
                session.flush() # Generate ID without committing yet

            # Check variations
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
    # The raw data string
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
        print("Populating Categories with fixed IDs...")
        
        # Split into lines
        lines = raw_text.strip().split('\n')
        
        for line in lines:
            if not line: continue
            
            # Split "1. Бял хляб" into ["1", " Бял хляб"]
            # We split only on the FIRST dot, just in case the name has a dot in it
            parts = line.split('.', 1)
            
            if len(parts) == 2:
                cat_id = int(parts[0].strip())
                cat_name = parts[1].strip()
                
                # Check if this ID exists
                stmt = select(Category).where(Category.id == cat_id)
                existing_cat = session.execute(stmt).scalar_one_or_none()
                
                if not existing_cat:
                    # Create new with explicit ID
                    new_cat = Category(id=cat_id, name=cat_name)
                    session.add(new_cat)
                else:
                    # Optional: Update the name if it changed
                    if existing_cat.name != cat_name:
                        existing_cat.name = cat_name
        
        session.commit()
        print("Categories populated successfully.")

def get_coords(address):
    if not address:
        return None

    # 1. INITIAL CLEANUP
    # Replace the common typo "rp." with "гр." (city)
    address = address.replace("rp.", "гр.")
    # Remove leading/trailing quotes or weird whitespace
    address = address.strip(' "')

    # 2. PATTERN-BASED NOISE REMOVAL
    # Pattern A: "153 - Русе/ул. Стрешер..." -> Keep "Русе, ул. Стрешер..."
    if '/' in address and ' - ' in address:
        address = address.split(' - ')[-1].replace('/', ', ')

    # Pattern B: "Кауфланд София-Младост - гр.София..." -> Keep "гр.София..."
    elif ' - ' in address:
        address = address.split(' - ')[-1]

    # Pattern C: "Билла 155 СОФИЯ БУЛ..." -> Remove "Билла 155"
    # Pattern D: "10 Метро София 1 - 1784..." -> Remove "10 Метро София 1 -"
    address = re.sub(r'^(Билла|Метро|Kaufland|Кауфланд)\s+\d+\s+', '', address, flags=re.I)
    address = re.sub(r'^\d+\s+(Метро|Билла|Билла|Кауфланд)\s+', '', address, flags=re.I)

    # 3. FINAL REFINEMENT
    # Remove ZIP codes (4 digits) that often confuse Photon
    address = re.sub(r'\b\d{4}\b', '', address)
    # Clean up excess spaces or dashes left at the start
    address = re.sub(r'^[\s\-\,]+', '', address).strip()

    try:
        url = "https://photon.komoot.io/api/"
        # We append Bulgaria to ensure we don't end up in Sofia, New Mexico
        params = {"q": f"{address}, Bulgaria", "limit": 1}
        headers = {"User-Agent": "Mozilla/5.0 (StoreApp/1.0)"}
        
        # Respect the API with a small delay
        time.sleep(0.5) 
        
        r = requests.get(url, params=params, headers=headers, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            if data and data.get('features'):
                # Photon returns [lon, lat]
                lon, lat = data['features'][0]['geometry']['coordinates']
                print(f"  [Found] {address} -> {lat}, {lon}")
                return f"{lat}, {lon}"
            else:
                print(f"  [Not Found] {address}")
        elif r.status_code == 403:
            print("  (!) Rate limited. Sleeping...")
            time.sleep(2)
            
    except Exception as e:
        print(f"  (!) Error: {e}")
        
    return None

def parse_product(product_string):
    product_string = product_string.replace('~', '').strip()
    clean_name = product_string
    quantity = None
    unit = 'бр'
    full_match_text = ""
    
    # Regex patterns for units - Added 'M' for Bulgarian shorthand (360M = 360ML)
    unit_pattern = r'(КГ|ГР|Г|МЛ|Л|БР|KG|GR|G|ML|L|MЛ|КG|KГ|M)'
    
    # 1. Pattern for ranges like 300/500ГР
    range_pattern = r'(\d+)/(\d+)\s*' + unit_pattern
    # 2. Pattern for multipacks like 2x500Г
    multi_pattern = r'(\d+)\s*[xхXХ]\s*(\d+[\.,]?\d*)\s*' + unit_pattern
    # 3. Standard weight pattern like 500ГР
    std_pattern = r'(\d+[\.,]?\d*)\s*' + unit_pattern + r'\b'

    range_match = re.search(range_pattern, product_string, re.I)
    multi_match = re.search(multi_pattern, product_string, re.I)
    std_match = re.search(std_pattern, product_string, re.I)

    if range_match:
        # Calculate the average of the range (e.g., 300/500 becomes 400)
        val1 = float(range_match.group(1))
        val2 = float(range_match.group(2))
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
        # Fallback for products with no detectable weight/count
        return clean_name, 1.0, 'бр'

    # Conversion dictionary including the 'M' shorthand
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

    # Intercept placeholder weights (preventing 1g errors)
    if quantity is not None and quantity <= 0.001:
        quantity = 1.0
        unit = 'бр'

    # Clean the product name by removing the text that matched the weight/unit
    if full_match_text:
        clean_name = product_string.replace(full_match_text, "").strip()
        # Clean up trailing punctuation or spaces
        clean_name = re.sub(r'^[\s\.\-\,]+|[\s\.\-\,]+$', '', clean_name)

    return clean_name, quantity, unit

def process_feed(url, engine):
    # Load chain names mapping from DB
    with Session(engine) as session:
        chains = {cn.name.lower(): cn.chain_id for cn in session.execute(select(ChainName)).scalars()}
        units = {u.name: u.id for u in session.execute(select(Unit)).scalars()}

    print(f"Downloading feed...")
    resp = requests.get(url)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        for filename in z.namelist():
            if not filename.endswith('.csv'): continue
            
            # Find which chain this file belongs to
            matched_id = None
            # if 'билла' in filename.lower():
            matched_id = next((cid for name, cid in chains.items() if name in filename.lower()), None)
            if not matched_id: continue

            print(f"Processing: {filename}")
            with z.open(filename) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'))
                
                previous_addr = ""
                with Session(engine) as session:
                    for row in reader:
                        addr = row.get("Търговски обект", "").strip()
                        city = row.get("Населено място", "").strip()
                        prod_raw = row.get("Наименование на продукта", "").strip()
                        
                        # 1. Get/Create Store
                        if previous_addr != addr:
                            stmt_store = select(Store).where(Store.address == addr)
                            store = session.execute(stmt_store).scalar_one_or_none()

                            if store is None:
                                # Remove store numbers (e.g. "10 Метро София" -> "Метро София")
                                clean_addr = re.sub(r'^\d+\s+', '', addr) 
                                # Remove ZIP codes if they are stuck to city names
                                clean_addr = re.sub(r'\d{4,}', '', clean_addr)

                                time.sleep(2)
                                coords = get_coords(f"{city}, {addr}")
                                store = Store(address=addr, populated_area=city, chain_id=matched_id, coords=coords)
                                session.add(store)
                                session.flush() # Get ID
                                time.sleep(1) # Respect Photon rate limit
                            previous_addr = addr
                        # 2. Parse Product
                        p_name, p_qty, p_unit_str = parse_product(prod_raw)
                        
                        # 3. Handle Unit
                        unit_id = units.get(p_unit_str)

                        # 4. Save Product
                        try:
                            price_raw = row.get("Цена на дребно", 0) or row.get("Цена в промоция", 0)
                            final_price = float(str(price_raw).replace(',', '.'))
                            cat_id = int(row.get("Категория", 0)) or None
                            
                            session.add(Product(
                                name=p_name, quantity=p_qty, price=final_price,
                                category_id=cat_id, store_id=store.id, unit_id=unit_id
                            ))
                        except ValueError: continue

                    session.commit()

def testing():
    file_path = "price_comparison.db"
    if os.path.exists(file_path):
        os.remove(file_path)
    
    engine = create_db()

    # Run initial setup (only once)
    populate_chains(engine, stores)
    populate_chain_names(engine, stores)
    populate_units(engine)
    populate_categories(engine)

    # Process files
    url = 'https://kolkostruva.bg/opendata_files/2026-01-04.zip'
    process_feed(url, engine)

#engine = create_db()
testing()
show_all_data(engine)
