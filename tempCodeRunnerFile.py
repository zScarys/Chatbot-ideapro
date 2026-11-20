

# ==========================================
# CONFIGURACIÓN
# ==========================================
#JOSELUIS

load_dotenv()
app = Flask(__name__)

# La base de datos vive en la carpeta data/, junto a este archivo.
CARPETA_BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(CARPETA_BASE, "d