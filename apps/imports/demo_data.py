"""Справочные данные для генератора демонстрационного наполнения.

Данные реалистичные, но синтетические: модельные ряды и параметры взяты по
открытым линейкам вендоров, конкретные значения генерируются детерминированно.
Ничего не парсится с чужого сайта — демо должно поднматься одной командой и
воспроизводиться байт в байт.
"""

BRANDS = [
    ("komatsu", "Komatsu", "Японская техника для строительства, горных работ и логистики."),
    ("bomag", "BOMAG", "Немецкое дорожно-строительное оборудование: катки и асфальтоукладчики."),
    ("manitou", "Manitou", "Французские телескопические и вилочные погрузчики."),
    ("denyo", "Denyo", "Дизельные генераторы и сварочные агрегаты."),
    ("generac-mobile", "Generac Mobile", "Мобильные электростанции и осветительные мачты."),
    ("terex", "Terex Cranes", "Гусеничные и автомобильные краны."),
    ("techking", "TECHKING", "Шины для карьерной и строительной техники."),
]

# Дерево категорий: (slug, название, [дочерние])
CATEGORIES = [
    (
        "stroitelnaya-i-dorozhnaya",
        "Строительная и дорожная техника",
        [
            ("ekskavatory", "Экскаваторы"),
            ("bulldozery", "Бульдозеры"),
            ("frontalnye-pogruzchiki", "Фронтальные погрузчики"),
            ("dorozhnye-katki", "Дорожные катки"),
            ("samosvaly", "Карьерные самосвалы"),
        ],
    ),
    (
        "skladskaya",
        "Складская техника",
        [
            ("vilochnye-pogruzchiki", "Вилочные погрузчики"),
            ("teleskopicheskie-pogruzchiki", "Телескопические погрузчики"),
        ],
    ),
    (
        "portovaya",
        "Портовая техника",
        [
            ("krany", "Краны"),
        ],
    ),
    (
        "elektrooborudovanie",
        "Электрооборудование",
        [
            ("generatory", "Генераторы"),
        ],
    ),
]

MACHINE_TYPES = [
    ("ekskavator", "Экскаватор", "Экскаваторы"),
    ("bulldozer", "Бульдозер", "Бульдозеры"),
    ("frontalnyy-pogruzchik", "Фронтальный погрузчик", "Фронтальные погрузчики"),
    ("vilochnyy-pogruzchik", "Вилочный погрузчик", "Вилочные погрузчики"),
    ("teleskopicheskiy-pogruzchik", "Телескопический погрузчик", "Телескопические погрузчики"),
    ("dorozhnyy-katok", "Дорожный каток", "Дорожные катки"),
    ("samosval", "Карьерный самосвал", "Карьерные самосвалы"),
    ("kran", "Кран", "Краны"),
    ("generator", "Генератор", "Генераторы"),
]

SPEC_GROUPS = [
    ("dvigatel", "Двигатель", 10),
    ("massy-i-gabarity", "Массы и габариты", 20),
    ("rabochee-oborudovanie", "Рабочее оборудование", 30),
    ("khodovaya-chast", "Ходовая часть", 40),
    ("osnaschenie", "Оснащение", 50),
]

# (код, название, группа, единица, тип, фильтруемый, в плитке, знаков, синонимы)
SPEC_KEYS = [
    (
        "engine_power",
        "Мощность двигателя",
        "dvigatel",
        "кВт",
        "number",
        True,
        True,
        0,
        ["Мощность двиг.", "Мощность двигателя, кВт", "Мощность", "Мощность двиг., кВт"],
    ),
    (
        "engine_model",
        "Модель двигателя",
        "dvigatel",
        "",
        "string",
        False,
        False,
        0,
        ["Двигатель", "Тип двигателя"],
    ),
    (
        "fuel_tank",
        "Объём топливного бака",
        "dvigatel",
        "л",
        "number",
        False,
        False,
        0,
        ["Топливный бак", "Ёмкость бака"],
    ),
    (
        "emission_stage",
        "Экологический класс",
        "dvigatel",
        "",
        "option",
        True,
        False,
        0,
        ["Экологический стандарт", "Нормы токсичности"],
    ),
    (
        "operating_weight",
        "Эксплуатационная масса",
        "massy-i-gabarity",
        "кг",
        "number",
        True,
        True,
        0,
        ["Масса", "Рабочая масса", "Эксплуатационная масса, кг"],
    ),
    (
        "transport_length",
        "Транспортная длина",
        "massy-i-gabarity",
        "мм",
        "number",
        False,
        False,
        0,
        ["Длина"],
    ),
    (
        "bucket_capacity",
        "Объём ковша",
        "rabochee-oborudovanie",
        "м³",
        "number",
        True,
        True,
        2,
        ["Ковш", "Вместимость ковша", "Объём ковша, м3"],
    ),
    (
        "digging_depth",
        "Глубина копания",
        "rabochee-oborudovanie",
        "м",
        "number",
        True,
        False,
        1,
        ["Макс. глубина копания", "Глубина копания, м"],
    ),
    (
        "lifting_capacity",
        "Грузоподъёмность",
        "rabochee-oborudovanie",
        "кг",
        "number",
        True,
        True,
        0,
        ["Грузоподъёмность, кг", "Максимальная грузоподъёмность"],
    ),
    (
        "lift_height",
        "Высота подъёма",
        "rabochee-oborudovanie",
        "м",
        "number",
        True,
        True,
        1,
        ["Максимальная высота подъёма", "Высота подъёма, м"],
    ),
    (
        "drum_width",
        "Ширина вальца",
        "rabochee-oborudovanie",
        "мм",
        "number",
        True,
        True,
        0,
        ["Ширина уплотняемой полосы", "Ширина вальца, мм"],
    ),
    (
        "power_output",
        "Выходная мощность",
        "rabochee-oborudovanie",
        "кВА",
        "number",
        True,
        True,
        0,
        ["Номинальная мощность", "Выходная мощность, кВА"],
    ),
    (
        "max_speed",
        "Максимальная скорость",
        "khodovaya-chast",
        "км/ч",
        "number",
        False,
        False,
        1,
        ["Скорость передвижения"],
    ),
    (
        "track_type",
        "Тип ходовой",
        "khodovaya-chast",
        "",
        "option",
        True,
        False,
        0,
        ["Ходовая часть", "Тип шасси"],
    ),
    (
        "cabin_ac",
        "Кондиционер в кабине",
        "osnaschenie",
        "",
        "bool",
        True,
        False,
        0,
        ["Кондиционер", "Климат-контроль"],
    ),
]

SPEC_OPTIONS = {
    "emission_stage": [
        ("stage-2", "Stage II / Tier 2"),
        ("stage-3a", "Stage IIIA / Tier 3"),
        ("stage-5", "Stage V / Tier 4 Final"),
    ],
    "track_type": [
        ("gusenichnaya", "Гусеничная"),
        ("kolesnaya", "Колёсная"),
    ],
}

# Типы техники и применимые к ним параметры.
TYPE_SPECS = {
    "ekskavator": [
        "engine_power",
        "engine_model",
        "fuel_tank",
        "emission_stage",
        "operating_weight",
        "transport_length",
        "bucket_capacity",
        "digging_depth",
        "max_speed",
        "track_type",
        "cabin_ac",
    ],
    "bulldozer": [
        "engine_power",
        "engine_model",
        "fuel_tank",
        "emission_stage",
        "operating_weight",
        "transport_length",
        "bucket_capacity",
        "max_speed",
        "track_type",
        "cabin_ac",
    ],
    "frontalnyy-pogruzchik": [
        "engine_power",
        "engine_model",
        "fuel_tank",
        "emission_stage",
        "operating_weight",
        "bucket_capacity",
        "lifting_capacity",
        "max_speed",
        "track_type",
        "cabin_ac",
    ],
    "vilochnyy-pogruzchik": [
        "engine_power",
        "engine_model",
        "operating_weight",
        "lifting_capacity",
        "lift_height",
        "max_speed",
        "cabin_ac",
    ],
    "teleskopicheskiy-pogruzchik": [
        "engine_power",
        "engine_model",
        "operating_weight",
        "lifting_capacity",
        "lift_height",
        "max_speed",
        "emission_stage",
        "cabin_ac",
    ],
    "dorozhnyy-katok": [
        "engine_power",
        "engine_model",
        "operating_weight",
        "drum_width",
        "max_speed",
        "emission_stage",
        "cabin_ac",
    ],
    "samosval": [
        "engine_power",
        "engine_model",
        "fuel_tank",
        "operating_weight",
        "lifting_capacity",
        "max_speed",
        "track_type",
        "cabin_ac",
    ],
    "kran": [
        "engine_power",
        "engine_model",
        "operating_weight",
        "lifting_capacity",
        "lift_height",
        "track_type",
        "cabin_ac",
    ],
    "generator": [
        "engine_power",
        "engine_model",
        "fuel_tank",
        "power_output",
        "operating_weight",
        "emission_stage",
    ],
}

# Диапазоны генерации значений: (минимум, максимум) по типу техники.
SPEC_RANGES = {
    "ekskavator": {
        "engine_power": (80, 460),
        "operating_weight": (13000, 96000),
        "bucket_capacity": (0.5, 5.2),
        "digging_depth": (5.0, 8.4),
        "transport_length": (7500, 13500),
        "fuel_tank": (300, 1250),
        "max_speed": (3.0, 5.5),
    },
    "bulldozer": {
        "engine_power": (120, 260),
        "operating_weight": (18000, 44000),
        "bucket_capacity": (3.0, 9.4),
        "transport_length": (5200, 7400),
        "fuel_tank": (400, 900),
        "max_speed": (3.5, 11.0),
    },
    "frontalnyy-pogruzchik": {
        "engine_power": (120, 400),
        "operating_weight": (15000, 52000),
        "bucket_capacity": (2.5, 6.5),
        "lifting_capacity": (4000, 12000),
        "fuel_tank": (280, 700),
        "max_speed": (20.0, 38.0),
    },
    "vilochnyy-pogruzchik": {
        "engine_power": (35, 90),
        "operating_weight": (3500, 9500),
        "lifting_capacity": (1500, 5000),
        "lift_height": (3.0, 7.0),
        "max_speed": (17.0, 25.0),
    },
    "teleskopicheskiy-pogruzchik": {
        "engine_power": (55, 105),
        "operating_weight": (6500, 12500),
        "lifting_capacity": (2500, 5000),
        "lift_height": (6.0, 18.0),
        "max_speed": (25.0, 40.0),
    },
    "dorozhnyy-katok": {
        "engine_power": (55, 160),
        "operating_weight": (7000, 25000),
        "drum_width": (1300, 2200),
        "max_speed": (6.0, 12.0),
    },
    "samosval": {
        "engine_power": (250, 780),
        "operating_weight": (28000, 78000),
        "lifting_capacity": (25000, 63000),
        "fuel_tank": (400, 1100),
        "max_speed": (45.0, 65.0),
    },
    "kran": {
        "engine_power": (180, 400),
        "operating_weight": (36000, 96000),
        "lifting_capacity": (55000, 130000),
        "lift_height": (40.0, 68.0),
    },
    "generator": {
        "engine_power": (20, 320),
        "power_output": (25, 400),
        "operating_weight": (700, 4200),
        "fuel_tank": (60, 700),
    },
}

# (бренд, тип, категория, [модели])
MACHINE_LINES = [
    (
        "komatsu",
        "ekskavator",
        "ekskavatory",
        [
            "PC130-8",
            "PC160LC-8",
            "PC200-8",
            "PC210LC-11",
            "PC220-8",
            "PC240LC-11",
            "PC300-8",
            "PC350LC-8",
            "PC400-8",
            "PC490LC-11",
            "PC650-8",
            "PC750-7",
            "PC800-8",
            "PC1250-8",
        ],
    ),
    (
        "komatsu",
        "bulldozer",
        "bulldozery",
        [
            "D51EX-24",
            "D61EX-24",
            "D65EX-18",
            "D85EX-15",
            "D155A-6",
            "D275A-5",
            "D375A-6",
        ],
    ),
    (
        "komatsu",
        "frontalnyy-pogruzchik",
        "frontalnye-pogruzchiki",
        [
            "WA200-8",
            "WA270-8",
            "WA320-8",
            "WA380-8",
            "WA430-6",
            "WA470-8",
            "WA500-8",
            "WA600-6",
            "WA800-3",
        ],
    ),
    (
        "komatsu",
        "samosval",
        "samosvaly",
        [
            "HM300-5",
            "HM400-5",
            "HD405-8",
            "HD465-8",
            "HD605-8",
        ],
    ),
    (
        "komatsu",
        "vilochnyy-pogruzchik",
        "vilochnye-pogruzchiki",
        [
            "FD15T-21",
            "FD20T-17",
            "FD25T-17",
            "FD30T-17",
            "FD35AT-17",
            "FG15T-21",
            "FG25T-17",
            "FG35AT-17",
        ],
    ),
    (
        "bomag",
        "dorozhnyy-katok",
        "dorozhnye-katki",
        [
            "BW 138 AD-5",
            "BW 154 AP-4",
            "BW 161 AD-5",
            "BW 177 D-5",
            "BW 202 AD-5",
            "BW 213 D-5",
            "BW 213 DH-5",
            "BW 219 DH-5",
            "BW 226 DH-5",
        ],
    ),
    (
        "manitou",
        "teleskopicheskiy-pogruzchik",
        "teleskopicheskie-pogruzchiki",
        [
            "MT 625 H",
            "MT 733",
            "MT 933",
            "MT 1135",
            "MT 1335",
            "MT 1440",
            "MT 1840",
            "MLT 635-130",
            "MLT 737-130",
            "MLT 841-145",
        ],
    ),
    (
        "manitou",
        "vilochnyy-pogruzchik",
        "vilochnye-pogruzchiki",
        [
            "MI 25 D",
            "MI 30 D",
            "MI 35 D",
            "MSI 30 T",
            "MSI 35 T",
        ],
    ),
    (
        "denyo",
        "generator",
        "generatory",
        [
            "DCA-25ESK",
            "DCA-45ESK",
            "DCA-60ESK",
            "DCA-90ESK",
            "DCA-125ESK",
            "DCA-150ESK",
            "DCA-220ESK",
            "DCA-300ESK",
        ],
    ),
    (
        "generac-mobile",
        "generator",
        "generatory",
        [
            "MGG 25",
            "MGG 40",
            "MGG 60",
            "MGG 100",
            "MGG 150",
            "MGG 220",
            "MGG 330",
        ],
    ),
    (
        "terex",
        "kran",
        "krany",
        [
            "Demag AC 45 City",
            "Demag AC 55-3",
            "Demag AC 100-4L",
            "Demag AC 130-5",
            "RT 90",
            "RT 100US",
        ],
    ),
]

# Категории и позиции запчастей: (slug, название, [(артикул, наименование, бренд)])
PART_CATEGORIES = [
    ("originalnye-zapchasti", "Оригинальные запчасти"),
    ("khodovaya-chast", "Ходовая часть"),
    ("filtry", "Фильтры"),
    ("kovshi-i-zuby", "Ковши и зубья"),
    ("gidromoloty", "Гидромолоты"),
    ("rvd", "РВД и гидравлика"),
    ("smazochnye-materialy", "Смазочные материалы"),
    ("shiny", "Шины"),
]

PART_TEMPLATES = {
    "filtry": [
        ("Фильтр масляный", "600-211-{n}"),
        ("Фильтр топливный", "600-311-{n}"),
        ("Фильтр воздушный основной", "600-185-{n}"),
        ("Фильтр гидравлический", "07063-{n}"),
        ("Фильтр сепаратора", "600-319-{n}"),
    ],
    "khodovaya-chast": [
        ("Башмак гусеницы", "20Y-32-{n}"),
        ("Каток опорный", "20Y-30-{n}"),
        ("Звёздочка ведущая", "20Y-27-{n}"),
        ("Цепь гусеничная", "207-32-{n}"),
    ],
    "kovshi-i-zuby": [
        ("Зуб ковша", "205-70-{n}"),
        ("Коронка ковша", "207-70-{n}"),
        ("Адаптер зуба", "209-70-{n}"),
        ("Режущая кромка", "195-71-{n}"),
    ],
    "rvd": [
        ("Рукав высокого давления", "07000-{n}"),
        ("Уплотнительное кольцо", "07000-15{n}"),
        ("Насос гидравлический", "708-2L-{n}"),
    ],
    "smazochnye-materialy": [
        ("Масло моторное Komatsu EO15W40DH, 20 л", "SAE-15W40-{n}"),
        ("Масло гидравлическое Komatsu HO46-HM, 20 л", "SAE-HO46-{n}"),
        ("Смазка G2-LI, 400 г", "SYG-400-{n}"),
    ],
    "gidromoloty": [
        ("Гидромолот в сборе", "JTHB-{n}"),
        ("Пика гидромолота", "JTHB-P{n}"),
        ("Комплект уплотнений гидромолота", "JTHB-S{n}"),
    ],
    "shiny": [
        ("Шина карьерная TECHKING ETSM", "TK-{n}"),
        ("Шина индустриальная TECHKING", "TKI-{n}"),
    ],
    "originalnye-zapchasti": [
        ("Ремень приводной", "04121-{n}"),
        ("Датчик давления масла", "7861-93-{n}"),
        ("Стартер", "600-813-{n}"),
        ("Генератор зарядки", "600-825-{n}"),
    ],
}

SERVICE_CATEGORIES = [
    ("to-i-remont", "ТО и ремонт"),
    ("diagnostika", "Диагностика"),
    ("analiz-masel", "Анализ масел"),
    ("vyezd-na-obekt", "Выезд на объект"),
    ("obuchenie", "Обучение"),
    ("shinomontazh", "Шиномонтаж спецтехники"),
]

# (slug, название, категория, цена от, примечание, срок, выезд)
SERVICES = [
    (
        "planovoe-to-komatsu",
        "Плановое ТО техники Komatsu",
        "to-i-remont",
        18000,
        "за нормо-час работ",
        "1–2 дня",
        False,
    ),
    (
        "kapitalnyy-remont-dvigatelya",
        "Капитальный ремонт двигателя",
        "to-i-remont",
        350000,
        "в зависимости от модели",
        "10–20 дней",
        False,
    ),
    (
        "remont-gidravliki",
        "Ремонт гидравлики и РВД",
        "to-i-remont",
        12000,
        "за нормо-час",
        "1–3 дня",
        False,
    ),
    (
        "zamena-khodovoy",
        "Замена элементов ходовой части",
        "to-i-remont",
        45000,
        "без стоимости запчастей",
        "2–4 дня",
        False,
    ),
    (
        "kompyuternaya-diagnostika",
        "Компьютерная диагностика",
        "diagnostika",
        9000,
        "за одну единицу техники",
        "от 3 часов",
        True,
    ),
    (
        "diagnostika-komtrax",
        "Диагностика по данным KOMTRAX",
        "diagnostika",
        None,
        "по договору обслуживания",
        "1 день",
        False,
    ),
    (
        "laboratornyy-analiz-masel",
        "Лабораторный анализ масел",
        "analiz-masel",
        4500,
        "за одну пробу",
        "3–5 дней",
        False,
    ),
    (
        "programma-monitoringa-masel",
        "Программа мониторинга масел на год",
        "analiz-masel",
        48000,
        "за единицу техники в год",
        "по графику",
        False,
    ),
    (
        "vyezdnoy-remont",
        "Выездной ремонт на объекте",
        "vyezd-na-obekt",
        15000,
        "плюс километраж",
        "в течение 24 часов",
        True,
    ),
    (
        "avariynyy-vyezd-24-7",
        "Аварийный выезд 24/7",
        "vyezd-na-obekt",
        25000,
        "круглосуточно",
        "в течение 6 часов",
        True,
    ),
    (
        "obuchenie-operatorov",
        "Обучение операторов спецтехники",
        "obuchenie",
        32000,
        "за одного слушателя",
        "5 дней",
        False,
    ),
    (
        "obuchenie-mekhanikov",
        "Обучение механиков по Komatsu",
        "obuchenie",
        46000,
        "за одного слушателя",
        "10 дней",
        False,
    ),
    (
        "stropalshchik",
        "Подготовка стропальщиков",
        "obuchenie",
        12000,
        "за одного слушателя",
        "3 дня",
        False,
    ),
    (
        "shinomontazh-karernyy",
        "Шиномонтаж карьерной техники",
        "shinomontazh",
        22000,
        "за колесо",
        "от 4 часов",
        True,
    ),
    (
        "podbor-shin",
        "Подбор шин под условия эксплуатации",
        "shinomontazh",
        None,
        "бесплатно при покупке",
        "1 день",
        False,
    ),
]

DEPARTMENTS = [
    ("prodazhi-tehniki", "Отдел продаж техники", "sales@modernmachinery.example"),
    ("zapchasti", "Отдел запасных частей", "parts@modernmachinery.example"),
    ("servis", "Сервисная служба", "service@modernmachinery.example"),
    (
        "skladskoe-oborudovanie",
        "Складское и погрузочное оборудование",
        "forklift@modernmachinery.example",
    ),
    ("uchebnyy-centr", "Учебный центр", "training@modernmachinery.example"),
]

EMPLOYEES = [
    (
        "Ковалёв Андрей Сергеевич",
        "Руководитель филиала",
        None,
        [("phone", "+7 (4212) 45-67-00", "")],
    ),
    (
        "Литвинов Павел Игоревич",
        "Менеджер по продаже техники",
        "prodazhi-tehniki",
        [("phone", "+7 (4212) 45-67-12", "1201"), ("mobile", "+7 (914) 543-21-09", "")],
    ),
    (
        "Соколова Мария Викторовна",
        "Менеджер по запасным частям",
        "zapchasti",
        [("phone", "+7 (4212) 45-67-24", "1954"), ("email", "parts@modernmachinery.example", "")],
    ),
    (
        "Гордеев Илья Романович",
        "Руководитель сервисной службы",
        "servis",
        [("phone", "+7 (4212) 45-67-31", ""), ("whatsapp", "+7 (914) 771-05-42", "")],
    ),
    (
        "Ерёмин Виктор Петрович",
        "Менеджер по складскому оборудованию",
        "skladskoe-oborudovanie",
        [("phone", "+7 (4212) 45-67-38", ""), ("email", "forklift@modernmachinery.example", "")],
    ),
    (
        "Чернова Ольга Дмитриевна",
        "Специалист учебного центра",
        "uchebnyy-centr",
        [("phone", "+7 (4212) 45-67-44", "")],
    ),
]

NEWS = [
    (
        "Хабаровский филиал расширил склад запасных частей",
        "Складские мощности выросли в полтора раза, срок поставки ходовых позиций "
        "сократился до одного дня.",
    ),
    (
        "Новая линейка катков BOMAG на складе в Хабаровске",
        "В наличии появились катки BW 213 D-5 и BW 219 DH-5 для дорожного строительства.",
    ),
    (
        "Лаборатория анализа масел приняла тысячную пробу",
        "Программа мониторинга масел помогает заказчикам предупреждать отказы "
        "гидравлики до поломки.",
    ),
    (
        "Учебный центр запустил курс для механиков по гидравлике Komatsu",
        "Ближайший поток стартует в следующем месяце, набор открыт.",
    ),
    (
        "Сервисная служба перешла на круглосуточный режим выездов",
        "Аварийная бригада выезжает на объект в течение шести часов после заявки.",
    ),
]

VACANCIES = [
    (
        "Сервисный инженер по спецтехнике",
        "servis",
        "Диагностика и ремонт техники Komatsu на площадке филиала и на объектах заказчика.",
        "Опыт работы с гидравликой от двух лет, готовность к командировкам по краю.",
        "от 150 000 ₽",
    ),
    (
        "Менеджер по продаже запасных частей",
        "zapchasti",
        "Работа с входящими заявками, подбор запчастей по каталогам, ведение клиентской базы.",
        "Опыт в продажах B2B, знание номенклатуры спецтехники приветствуется.",
        "от 110 000 ₽ плюс процент",
    ),
    (
        "Механик по складской технике",
        "skladskoe-oborudovanie",
        "Обслуживание вилочных и телескопических погрузчиков.",
        "Опыт обслуживания погрузчиков, действующее удостоверение.",
        "от 130 000 ₽",
    ),
]


# Посадочные подборки каталога под геозапросы.
# (slug, заголовок, бренд, тип техники, вступительный текст)
#
# Тексты написаны заново, а не скопированы с корпоративного сайта: дубли на
# одном домене — прямой путь к понижению обеих страниц в выдаче (раздел 7.3).
CATALOG_LANDINGS = [
    (
        "ekskavatory-komatsu-habarovsk",
        "Экскаваторы Komatsu в Хабаровске",
        "komatsu",
        "ekskavator",
        "Гусеничные экскаваторы Komatsu со склада филиала в Хабаровске: от компактных "
        "моделей для городского строительства до карьерных машин. Официальная гарантия, "
        "оригинальные запчасти и сервисное обслуживание на месте.",
    ),
    (
        "bulldozery-komatsu-habarovsk",
        "Бульдозеры Komatsu в Хабаровске",
        "komatsu",
        "bulldozer",
        "Бульдозеры Komatsu для дорожного строительства и разработки грунта. "
        "Подбираем модель под условия объекта, обслуживаем в сервисном центре филиала.",
    ),
    (
        "frontalnye-pogruzchiki-habarovsk",
        "Фронтальные погрузчики в Хабаровске",
        "komatsu",
        "frontalnyy-pogruzchik",
        "Фронтальные погрузчики Komatsu для складов, карьеров и портовых площадок. "
        "Наличие уточняйте у менеджера — часть моделей есть на складе в Хабаровске.",
    ),
    (
        "dorozhnye-katki-bomag-habarovsk",
        "Дорожные катки BOMAG в Хабаровске",
        "bomag",
        "dorozhnyy-katok",
        "Грунтовые и асфальтовые катки BOMAG для дорожных работ на Дальнем Востоке. "
        "Поставка со склада, обучение операторов, сервис с выездом на объект.",
    ),
    (
        "vilochnye-pogruzchiki-habarovsk",
        "Вилочные погрузчики в Хабаровске",
        None,
        "vilochnyy-pogruzchik",
        "Дизельные и газовые вилочные погрузчики для складов и производственных "
        "площадок. Отдельное направление филиала: свой менеджер и свой склад запчастей.",
    ),
    (
        "teleskopicheskie-pogruzchiki-manitou",
        "Телескопические погрузчики Manitou",
        "manitou",
        "teleskopicheskiy-pogruzchik",
        "Телескопические погрузчики Manitou: работа на высоте, погрузка сыпучих "
        "материалов, обслуживание животноводческих и складских комплексов.",
    ),
    (
        "generatory-habarovsk",
        "Дизельные генераторы в Хабаровске",
        None,
        "generator",
        "Дизельные электростанции Denyo и Generac Mobile для строительных площадок и "
        "резервного питания. Короткий цикл поставки, аренда обсуждается отдельно.",
    ),
    (
        "krany-habarovsk",
        "Автомобильные краны в Хабаровске",
        "terex",
        "kran",
        "Краны Terex и Demag для строительных и портовых работ. Поставка под заказ, "
        "сроки уточняйте у отдела продаж техники.",
    ),
]
