import random
import pytest
import datetime
from pathlib import Path

from app.services.weaviate.data_models.attraction_models import (
    AttractionModel
)
from app.services.weaviate.dataloader import (
    ChunkData,
    AttractionWithChunks,
)
from app.services.weaviate.weaviate_client import WeaviateClientWrapper, load_config_from_yaml
from app.services.weaviate.schema_manager import SchemaManager, parse_weaviate_schema_config
from app.services.weaviate.attraction_db_manager import AttractionDBManager


EMBEDDING_VECTOR_LENGTH = 1536
RAW_CHUNKS_DICTS = [
        [
            {
                "chunk_text": "The 'Dominican Church and Monastery' in Lviv, Ukraine is located in the city's Old Town, east of the market square. It was originally built as the Roman Catholic church of Corpus Christi, and today serves as the Greek Catholic church of the Holy Eucharist. The Dominican Order first arrived in Lviv during the 13th century and the first wooden church is said to have been built in 1234 within the Low Castle, founded by the wife of Leo I of Halych. That church burned down during a war in 1340. A new Gothic church, resembling the parish church in Kazimierz Dolny, was built on the present site in 1378 and later rebuilt after a fire in 1407 along with the monastery buildings. During the 16th century the complex was ravaged by several fires, nevertheless it continued to gradually rise in prosperity. In the 18th century the church's ceiling started cracking and it was decided in 1745 that the church had to be taken apart and replaced with a new one. In 1749 Józef Potocki laid the cornerstone for the present day Baroque church, commonly attributed to Jan de Witte. Between 1756 and 1761 Mikołaj Bazyli Potocki donated 236,000 złoty to the church and the Dominican monastery in Lviv, where his mother was buried. These donations funded the Potocki chapel in the church. The church was consecrated in 1764 by the Latin archbishop of Lviv Wacław Hieronim Sierakowski. The Dominicans managed to survive the reign of the Austrian emperor Joseph II, who closed many other monasteries. In 1865 a neo-baroque bell tower was added to the complex. In the years 1885–1914 a controversial renovation of the facade and interior was carried out. After World War II, the complex was occupied by the Soviets, used as a warehouse, and in the 1970s changed into a 'museum of religion and atheism'. With the collapse of the Soviet Union the church was given to the Ukrainian Greek Catholic Church and now serves as a parish church",
                "name": "The Church of the Holy Eucharist",
                "city": "Lviv",
                "embedding": [random.uniform(-1, 1) for i in range(EMBEDDING_VECTOR_LENGTH)],
                "administrative_area_level_1": "L'vivs'ka oblast",
                "administrative_area_level_2": None,
                "tags": ["church", "establishment", "place_of_worship", "point_of_interest"],
                "rating": 5,
                "place_id": "ChIJ8Tx7mwXdOkcRzMlP4KHfewk",
            },
            {
                "chunk_text": " bell tower was added to the complex. In the years 1885–1914 a controversial renovation of the facade and interior was carried out. After World War II, the complex was occupied by the Soviets, used as a warehouse, and in the 1970s changed into a 'museum of religion and atheism'. With the collapse of the Soviet Union the church was given to the Ukrainian Greek Catholic Church and now serves as a parish church. The monastery, however, has not yet been returned and still serves as a museum (renamed 'The Lviv Museum of History of Religion'). The church resembles the Karlskirche. It is built on the plan of the Greek Cross inscribed in an ellipsoid and topped with a monumental dome. Before 1946, the church contained a miraculous icon of the Blessed Virgin Mary, crowned by Pope Benedict XIV in 1751, which can be found today in the Dominican Basilica of St. Nicholas in Gdańsk, and an alabaster figure brought by St. Hyacinth from Mongol-sacked Kiev to Halych and later to Lviv, which now resides in Church of St. Giles in Kraków. In 2019, the Dominican Church was the location for the Gregorian's music video for their song ''Viva la Vida. Interior 360° panorama",
                "name": "The Church of the Holy Eucharist",
                "city": "Lviv",
                "embedding": [random.uniform(-1, 1) for i in range(EMBEDDING_VECTOR_LENGTH)],
                "administrative_area_level_1": "L'vivs'ka oblast",
                "administrative_area_level_2": None,
                "tags": ["church", "establishment", "place_of_worship", "point_of_interest"],
                "rating": 5,
                "place_id": "ChIJ8Tx7mwXdOkcRzMlP4KHfewk",
            }
        ],
        [
            {
                "chunk_text": "The 'Church of Sts. Olha and Elizabeth' is a Catholic church located in Lviv, Ukraine between the city's main rail station and the Old Town. It was originally built as a Western Catholic church and today serves as a Ukrainian Greek Catholic church. The church was built by the Latin Archbishop of Lviv, Józef Bilczewski in the years 1903–1911 as a parish church for the city's dynamically developing western suburb. It was designed by Polish architect Teodor Talowski, in the neo-Gothic style, similar to that of the Votive Church in Vienna. St. Elisabeth's, placed on a hill which is the watershed of the Baltic and Black Sea, with its facade flanked by two tall towers and an 85 m belfry on the north side with imposing spires was envisioned as Lviv's first landmark to greet visitors arriving in the city by train. In 1939, the church was damaged in a bombing raid but remained open until 1946. After the war, the building was used as a warehouse and fell further into ruin, until it was returned to faithful with the collapse of the Soviet Union. In 1991, a Ukrainian Greek Catholic church was established and the church was reconsecrated as the Church of Sts. Olha and Elizabeth.",
                "name": "St. Elizabeth's Church",
                "city": "Lviv",
                "embedding": [random.uniform(-1, 1) for i in range(EMBEDDING_VECTOR_LENGTH)],
                "administrative_area_level_1": "L'vivs'ka oblast",
                "administrative_area_level_2": None,
                "tags": ["church", "establishment", "place_of_worship", "point_of_interest"],
                "rating": 4.9,
                "place_id": "ChIJ1-28ZoLdOkcR4opcCjRrAnQ",
            }
        ]
]

RAW_ATTRACTIONS_LIST = [
    {
        "name": "The Church of the Holy Eucharist",
        "city": "Lviv",
        "address": "Muzeina Square,L'viv, L'vivs'ka oblast, Ukraine, 79000",
        "postal_code": "79000",
        "administrative_area_level_1": "L'vivs'ka oblast",
        "sublocality_level_1": "Halytskyi District",
        "coordinates": {"longitude": 24.0338232, "latitude": 49.8427498},
        "place_id": "ChIJ8Tx7mwXdOkcRzMlP4KHfewk",
        "maps_url": "https://maps.google.com/?cid=683385654822816204",
        "price_level": 0,
        "rating": 5,
        "reviews": [
            {
                "author_name": "Poseidónas Greek",
                "rating": 5,
                "text": 'The architecture of the building is beautiful.  Impressive is this construction of the former Dominican Cathedral.\nThis is one of the visiting cards of the cultural capital of Ukraine.\nExternal and internal design is collected in a unique ensemble.\n\nThe church is built in the late Baroque style on the Western European model.  Stone, in plan it depicts an elongated cross with an oval central part and two bell towers on the sides.  The church is glorified by a huge elliptical dome.  Massive double columns support galleries and lodges decorated with wooden statues by Lviv sculptors of the second half of the 18th century.  Above the galleries are drum columns supporting the dome.  Under the bath of the church is a quotation in Latin from the First Epistle to Timothy: "Soli Deo honor et gloria" ("Honor and praise to the One God"). I recommend to visit.',
                "time": datetime.datetime(2021, 8, 12, 13, 11, 9),
                "language": "en",
            },
            {
                "author_name": "l",
                "rating": 5,
                "text": "This is an amazing church, you can feel the power of God. When you walk in, your eyes have to process the splendor. In combination with the silence it gives you goosebumps…",
                "time": datetime.datetime(2023, 8, 25, 0, 4, 59),
                "language": "en",
            },
            {
                "author_name": "Vlad Bilousenko",
                "rating": 5,
                "text": "Wonderful place\nI love this view even more than central square",
                "time": datetime.datetime(2024, 8, 28, 8, 27, 19),
                "language": "en",
            },
            {
                "author_name": "Anastasia Sm",
                "rating": 5,
                "text": "A majestic church with a high ceiling, columns and many different details.",
                "time": datetime.datetime(2024, 5, 13, 21, 11, 59),
                "language": "en",
            },
            {
                "author_name": "ilyas gürbüz",
                "rating": 5,
                "text": "Such a amazing place. Not even close to the others. Very unique and magnificent church.",
                "time": datetime.datetime(2021, 7, 25, 16, 42, 11),
                "language": "en",
            },
        ],
        "tags": ["church", "establishment", "place_of_worship", "point_of_interest"],
        "wheelchair_accessible_entrance": False,
        "serves_beer": False,
        "serves_breakfast": False,
        "serves_brunch": False,
        "serves_dinner": False,
        "serves_lunch": False,
        "serves_vegetarian_food": False,
        "serves_wine": False,
        "takeout": False,
        "last_updated": "2025-08-28T09:52:55.341135+00:00",
    },
    {
        "name": "St. Elizabeth's Church",
        "city": "Lviv",
        "address": "Kropyvnyts'koho Square, 1, L'viv, L'vivs'ka oblast, Ukraine, 79000",
        "postal_code": "79000",
        "administrative_area_level_1": "L'vivs'ka oblast",
        "sublocality_level_1": "Halytskyi District",
        "coordinates": {"longitude": 24.0047246, "latitude": 49.8369484},
        "place_id": "ChIJ1-28ZoLdOkcR4opcCjRrAnQ",
        "phone_number": "+0322334073",
        "maps_url": "https://maps.google.com/?cid=8359361729609370338",
        "opening_hours": {
            "type": "weekly",
            "week_start": "2025-08-11",
            "week_end": "2025-08-17",
            "last_refreshed": "2025-08-17T21:00:00.049875+03:00",
            "weekly": {
                "monday": [{"start": "13:30", "end": "17:00"}],
                "tuesday": [{"start": "12:00", "end": "17:00"}],
                "wednesday": [{"start": "12:00", "end": "17:00"}],
                "thursday": [{"start": "12:00", "end": "17:00"}],
                "friday": [{"start": "12:00", "end": "17:00"}],
                "saturday": [{"start": "12:00", "end": "17:00"}],
                "sunday": [{"start": "12:00", "end": "17:00"}],
            },
        },
        "price_level": 0,
        "rating": 4.5,
        "reviews": [
            {
                "author_name": "Sven R.",
                "rating": 3,
                "text": "Nice church, nothing special inside, though.",
                "time": datetime.datetime(2025, 7, 1, 7, 51, 24),
                "language": "en",
            },
            {
                "author_name": "Tuğba Kurt",
                "rating": 5,
                "text": "Please do not go to up of church because there are many steps to top. And ladders are so hard to climb",
                "time": datetime.datetime(2021, 7, 26, 23, 12, 31),
                "language": "en",
            },
            {
                "author_name": "Dr Rakan",
                "rating": 3,
                "text": "Beautiful church ⛪️",
                "time": datetime.datetime(2021, 8, 16, 18, 35, 38),
                "language": "en",
            },
            {
                "author_name": "claus frandsen",
                "rating": 5,
                "text": "Very very beautiful, but old and need some repairs",
                "time": datetime.datetime(2021, 7, 2, 16, 30, 24),
                "language": "en",
            },
            {
                "author_name": "Dima Neverkovets",
                "rating": 5,
                "text": "Nice😍",
                "time": datetime.datetime(2022, 1, 11, 4, 7, 49),
                "language": "en",
            },
        ],
        "tags": ["church", "establishment", "place_of_worship", "point_of_interest"],
        "wheelchair_accessible_entrance": False,
        "serves_beer": False,
        "serves_breakfast": False,
        "serves_brunch": False,
        "serves_dinner": False,
        "serves_lunch": False,
        "serves_vegetarian_food": False,
        "serves_wine": False,
        "takeout": False,
        "last_updated": "2025-08-28T14:16:37.450534+00:00",
    }]

ATTRACTION_COLLECTION_NAME = "Attraction"
CHUNK_COLLECTION_NAME = "AttractionChunk"
CONNECTION_CONFIG = load_config_from_yaml("app/config/weaviate_connection.yaml")

@pytest.fixture
def client_wrapper():
    wrapper = WeaviateClientWrapper(CONNECTION_CONFIG)
    wrapper.connect()
    yield wrapper
    wrapper.disconnect()

@pytest.fixture(scope="function")
def db_manager_with_schema(client_wrapper):
    """
    A function-scoped fixture that provides a fully initialized AttractionDBManager
    with a guaranteed clean and fresh Weaviate schema for each test.
    
    Lifecycle:
    1. Connects to Weaviate.
    2. Tears down any old collections from previous runs.
    3. Creates new, clean collections ('Attraction' and 'AttractionChunk').
    4. Instantiates and yields an AttractionDBManager.
    5. After the test runs, tears down the collections to clean up.
    """
    client_wrapper = WeaviateClientWrapper(CONNECTION_CONFIG)
    client_wrapper.connect()
    client = client_wrapper.client
    schema_manager = SchemaManager(client)

    # --- Setup Phase ---
    # 1. Aggressively delete collections to ensure a clean slate
    try:
        schema_manager.delete_collection(ATTRACTION_COLLECTION_NAME)
    except Exception:
        pass  # Ignore errors if collection doesn't exist
    try:
        schema_manager.delete_collection(CHUNK_COLLECTION_NAME)
    except Exception:
        pass

    # 2. Create collections from schema files
    attraction_schema_path = Path("app/config/attraction_class_schema.yaml")
    attraction_schema = parse_weaviate_schema_config(str(attraction_schema_path))
    schema_manager.create_collection(attraction_schema)

    chunk_schema_path = Path("app/config/attraction_chunk_class_schema.yaml")
    if chunk_schema_path.exists():
        chunk_schema = parse_weaviate_schema_config(str(chunk_schema_path))
        schema_manager.create_collection(chunk_schema)

    # 3. Yield the ready-to-use DB manager
    db_manager = AttractionDBManager(client)
    yield db_manager

    # --- Teardown Phase ---
    # This code runs after each test finishes
    try:
        schema_manager.delete_collection(ATTRACTION_COLLECTION_NAME)
    except Exception:
        pass
    try:
        schema_manager.delete_collection(CHUNK_COLLECTION_NAME)
    except Exception:
        pass
    client_wrapper.disconnect()


# --- Simplified Data Fixtures ---
@pytest.fixture
def sample_attraction_data():
    """Returns a valid AttractionModel instance for testing."""
    return AttractionModel(**RAW_ATTRACTIONS_LIST[0])


@pytest.fixture
def sample_chunks_with_embeddings():
    """Return a list of ChunkData objects with embeddings."""
    chunks = []
    for c in RAW_CHUNKS_DICTS[0]:
        chunk = ChunkData(**c)
        chunks.append(chunk)
    
    return chunks


@pytest.fixture
def sample_attraction_with_chunks_list(sample_attraction_data, sample_chunks_with_embeddings):
    """Attraction + chunks bundled together."""
    return [AttractionWithChunks(
        source_file="test_file.txt",
        attraction=sample_attraction_data,
        chunks=sample_chunks_with_embeddings
    )]

@pytest.fixture
def sample_attraction_no_chunks_list(sample_attraction_data):
    """Attraction + chunks bundled together."""
    return [AttractionWithChunks(
        source_file="test_file.txt",
        attraction=sample_attraction_data,
        chunks=None
    )]

@pytest.fixture
def sample_multiple_attraction_with_chunks_list():
    res = []
    for idx, attraction in enumerate(RAW_ATTRACTIONS_LIST):
        chunk_list = [ChunkData(**c) for c in RAW_CHUNKS_DICTS[idx]]
        res.append(
            AttractionWithChunks(
                source_file="test_file.txt",
                attraction=AttractionModel(**attraction),
                chunks=chunk_list
            )
        )
    return res


