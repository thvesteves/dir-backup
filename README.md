# DIRBACKUP.PY
- Script to automate my backups, you can adapt it for your needs.
- I created this for my personal needs, i don't recommend using it in critical stuff.
- I DON'T HAVE ANY RESPONSIBILITY FOR ANY DAMAGE OR FILE LOST CAUSED BY THIS SCRIPT
- Platform: Windows
- Python version: 3.2+

## Description/How it works
- The script basically loops through a list of operations copying and removing files accordingly to the origin and destination informed.

- Files with same name and size are considered the same, so it won't copy. You can force some files to copy, see FILES_ALWAYS_REPLACE bellow.

- Two types of operations: copy and sync
	- copy: just copy the folders/files from origin to destination
	- sync: makes the destination identical to origin
- Params available:
	- enter_folders (bool) -> if False, it ignores folders, copy/sync only the files in the root of orig
	- try_to_move (bool) -> move files if possible, instead of copying (files that moved inside the origin and still exists in destination in a different folder structure)
	- overwrite (bool) -> always copy and overwrite files to destination

- By using the volume serial number, you don't need to worrie about changing configs if you plug/displug different devices. The script checks which drive letter(A:, E:, I:) your disks are mounted by the volume serial.
	
- Single log file: dir-backup.log

- Try to maintain the same file attributes from origin

## SETUP
#### 1. Discover your mounted disks volume serial, run the script:
```
py list-available-drives.py

{
    "99999999": "C:",
    "0000000000": "D:",
    "77777777": "G:",
    "444444444444": "I:"
}

```

#### 2. Define the CONSTANTS with the VOLUME SERIAL of your drives.
##### You can define using any name, i just found useful using this INTERNAL - EXTERNAL nomenclature.
Example:
```
#C:
INTERNAL_1_VSERIAL = 99999999
#D:
INTERNAL_2_VSERIAL = 0000000000

EXTERNAL_SEAGATE_1_VSERIAL = 77777777
EXTERNAL_SAMSUNG_1_VSERIAL = 444444444444
# create many as you need
# .
# .
```

#### 3. Set labels for your drives (just for logging).
Example:
```
DEVICELABELS = {
	INTERNAL_1_VSERIAL : 'INTERNAL C:',
	INTERNAL_2_VSERIAL : 'INTERNAL D:',
	EXTERNAL_SEAGATE_1_VSERIAL : 'EXTERNAL SEAGATE 1TB',
	EXTERNAL_SAMSUNG_1_VSERIAL : 'EXTERNAL SAMSUNG 2TB'
}
```
#### 4. Set files you want to not move. (Always uppercase)
##### Because they appear in different folders and are exactly the same
Example:
````
FILES_EXCEPTIONS = [
	'INFO.TXT',
	'TEST.TXT', 
]
````
#### 5. Set files you want to always overwrite. (Always uppercase)
Example:
```
FILES_ALWAYS_REPLACE = [
	'INFO.TXT'
]
```

#### 6. Set the operations.
Example:
```
OPERATIONS = [
	{
		'orig': r'\Users\myuser\Music', 
		'dest': r'\BACKUP\Music', 
		'type': 'sync',
		'orig_serial': INTERNAL_1_VSERIAL,
		'dest_serial': EXTERNAL_SEAGATE_1_VSERIAL,
	},

	{
		'orig': r'\Users\myuser\Downloads', 
		'dest': r'\BACKUP\Downloads', 
		'type': 'copy',
		'params': {
			'enter_folders': False
		},
		'orig_serial': INTERNAL_1_VSERIAL,
		'dest_serial': EXTERNAL_SEAGATE_1_VSERIAL
	},

	{
		'orig': r'\some-folder-in-root', 
		'dest': r'\BACKUP2\some-folder-in-root', 
		'type': 'copy',
		'params': {
			'try_to_move': True
		},
		'orig_serial': INTERNAL_2_VSERIAL,
		'dest_serial': EXTERNAL_SAMSUNG_1_VSERIAL,
	},

	{
		'orig': r'\Users\myuser\folder-full-of-txts',
		'dest': r'\BACKUP2\folder-full-of-txts',
		'type': 'copy',
		'params': {
			'overwrite': True
		},
		'orig_serial': INTERNAL_1_VSERIAL,
		'dest_serial': EXTERNAL_SAMSUNG_1_VSERIAL,	
	},
]
```

## Run:
```
py dirbackup.py
````