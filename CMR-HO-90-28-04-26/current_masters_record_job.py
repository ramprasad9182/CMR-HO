import xmlrpc.client
import logging
import sys
from datetime import datetime

# Logging setup
logging.basicConfig(
    filename='external_odoo_job.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logging.info("Job Started successfully")
# Odoo Configuration
url = "http://192.168.168.90/"
db = "CMR-VIZAG-108"
username = "admin"
password = "admin"

try:
    # Authenticate
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})

    if not uid:
        raise Exception("Authentication failed")

    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    # Call method
    result = models.execute_kw(
        db,
        uid,
        password,
        'nhcl.ho.store.master',
        'call_master_functions',
        [[]]
    )

    logging.info("Job executed successfully")
    print("Success:", result)

except Exception as e:
    logging.error(f"Job failed: {str(e)}")
    print("Error:", e)
    sys.exit(1)