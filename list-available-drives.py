import json
from dirbackup import get_serial_drive_map

d = get_serial_drive_map()
print(json.dumps(d, indent=4))