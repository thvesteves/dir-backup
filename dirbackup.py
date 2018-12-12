# Script to automate my backups, you can adapt it for your needs
# I created this for my personal needs, so i don't recommend using it in critical stuff.
# I DON'T HAVE ANY RESPONSIBILITY FOR ANY DAMAGE OR FILE LOST CAUSED BY THIS SCRIPT

import sys
#print sys.version
#import platform
#platform.system() == 'Windows'

import shutil
import os
import stat
import time
import win32file
import win32api
import win32con
import pywintypes
import json
import datetime

# import hashlib

# TODO: use a file to set the configurations

PATHLOG = r''
LOGFILE = PATHLOG + 'dir-backup.log'
# LOGFILE = PATHLOG + 'dir-backup-debug.log'
#encoding='utf-8': avoiding "UnicodeEncodeError: 'charmap' codec can't encode character"
#for python2 use:
#import io -> io.open()
if __name__ == '__main__':
	try:
		LOG = open(LOGFILE, 'a', encoding='utf-8')
	except IOError:
		print ('Error opening log file')
		sys.exit()


#C:
INTERNAL_1_VSERIAL = 99999999
#D:
INTERNAL_2_VSERIAL = 0000000000

EXTERNAL_SEAGATE_1_VSERIAL = 77777777
EXTERNAL_SAMSUNG_1_VSERIAL = 444444444444
# create many as you need
# .
# .

# labels used in LOG
DEVICELABELS = {
	INTERNAL_1_VSERIAL : 'INTERNAL C:',
	INTERNAL_2_VSERIAL : 'INTERNAL D:',
	EXTERNAL_SEAGATE_1_VSERIAL : 'EXTERNAL SEAGATE 1TB',
	EXTERNAL_SAMSUNG_1_VSERIAL : 'EXTERNAL SAMSUNG 2TB'
}

# some files that i don't want to move
# because they appear in different folders and are exactly the same
FILES_EXCEPTIONS = [
	'INFO.TXT',
	'TEST.TXT', 
]

FILES_ALWAYS_REPLACE = ['INFO.TXT']

# params available:
# enter_folders (bool) -> if False, it ignores folders, copy/sync only the files in the root of orig
# try_to_move (bool) -> move files if possible, instead of copying
# overwrite (bool) -> always copy and overwrite files to destination
# some examples (change to your needs):
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

ERROR_MSG = ''

#testing no disk space error
TESTSIZE = 100000
TESTSIZE_AFTER = 10

# 16*1024 = 16KiB
# 16*1024*1024 = 16MiB
# 16*1024*1024*1024 = 16GiB
# better to copy large files, and we can implement a progress bar in the future
# i found this googling, but i lost the link
def modified_copyfileobj(fsrc, fdst, len = 24*1024*1024):
	while 1:
		buf = fsrc.read(len)
		if not buf:
			break
		fdst.write(buf)
		#time.sleep(0.1)

# find the relative path for the destination file
# maintain the same directory structure for the destination
# path1 is the root and path2 is some file or dir bellow the root
def getNewPath(dest, file, path1, path2):
	relative = os.path.relpath(path1, path2)
	if relative == '.':
		relative = ''
	
	return os.path.join(dest, relative, file)

def isrecursive(params):
	return False if 'enter_folders' in params and params['enter_folders'] == False else True

def overwrite(params):
	return True if 'overwrite' in params and params['overwrite'] == True else False

def try_to_move(params):
	return True if 'try_to_move' in params and params['try_to_move'] == True else False

def setctime(originalpath, newfilepath):
	# can be needed for CreateFileW
	# if os.path.isdir(newfilepath):
	# 	newfilepath = '\\\\.\\' + newfilepath

	# win32con.FILE_ATTRIBUTE_NORMAL -> ACCESS DENIED ON DIRECTORIES
	# this fails sometimes, windows says another process still using the file
	# TODO: loop with a number of tries
	try:
		# translate to correct windows time format
		ctime = pywintypes.Time(os.path.getctime(originalpath))

		handle = win32file.CreateFile(
			newfilepath,
			win32con.GENERIC_WRITE,
			win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
			None,
			win32con.OPEN_EXISTING,
			win32con.FILE_FLAG_BACKUP_SEMANTICS, #for both, files and directories
			None
		)
		win32file.SetFileTime(handle, ctime, None, None)
		handle.close()

		# log('DEBUG: setctime - ORIGINALPATH: '+originalpath + ' - NEWFILEPATH: '+newfilepath)
	except Exception as e:
		log('\t\tERROR SETCTIME: ' + str(e))
		

# used for log the path without the common prefix
def onlysubpath(initialroot, currentroot):
	commonpath = os.path.commonpath([os.path.splitdrive(initialroot)[1], os.path.splitdrive(currentroot)[1]])
	return os.path.splitdrive(currentroot)[1].replace(commonpath, '', 1)

def set_original_attrs(orig, dest):
	# usually this will avoid an exception
	os.chmod(dest, stat.S_IWRITE)	

	# copy the HIDDEN attribute, if the source is HIDDEN
	try:
		# hidden attr does not work for some reason
		shutil.copystat(orig, dest)

		if win32con.FILE_ATTRIBUTE_HIDDEN & win32file.GetFileAttributesW(orig):
			win32file.SetFileAttributes(dest, win32con.FILE_ATTRIBUTE_HIDDEN)
	except Exception as e:
		log('\t\tERROR SET_ORIGINAL_ATTRS: ' + str(e))

	# maintain the creation time intact
	setctime(orig, dest)

def check_disk_space(originalpath, newfilepath):
	# the problem with this approach is that the file size on disk is different than the real size
	# user_free_bytes, total_bytes, total_free_bytes = win32api.GetDiskFreeSpaceEx(os.path.splitdrive(newfilepath)[0])
	# print(os.path.splitdrive(newfilepath)[0])
	# print('FREE SPACE: ', int(user_free_bytes/1024/1024/1024), 'GB')
	# print('FILESIZE:', os.path.getsize(originalpath))
	
	try:
		drive = os.path.splitdrive(newfilepath)[0]
		sectors_per_cluster, bytes_per_sector, number_free_clusters, total_number_clusters = win32api.GetDiskFreeSpace(drive)
		free_space_in_bytes = number_free_clusters * bytes_per_sector * sectors_per_cluster
		clusters = int(os.path.getsize(originalpath) / bytes_per_sector / sectors_per_cluster) + 1
		filesize_on_disk = clusters * sectors_per_cluster * bytes_per_sector

		# global TESTSIZE, TESTSIZE_AFTER
		# free_space_in_bytes = TESTSIZE
		if filesize_on_disk > free_space_in_bytes:
			on_error_log('NO DISK SPACE - ' + drive, 'No disk space')
			return False
		# TESTSIZE = TESTSIZE_AFTER

		return True
	except Exception as e:
		on_error_log('ERROR CHECK_DISK_SPACE: ' + str(e), 'Error checking disk space')
		return False

	# filesize = os.path.getsize(originalpath)
	# print('FREE SPACE: ', free_space_in_bytes)
	# print('FILESIZE:', filesize)
	# print('FILESIZE ON DISK:', filesize_on_disk)

def move_equals(orig, dest):
	count_moved = 0
	if not os.path.exists(orig) or not os.path.exists(dest):
		return count_moved

	global FILES_EXCEPTIONS
	files_orig = {}
	all_orig_dirs = []
	# get all files from origin
	for root, dirs, files in os.walk(orig):
		# store all source dirs, for use later to set file attributes in destination
		if len(dirs) > 0:
			for d in dirs:
				all_orig_dirs.append(os.path.join(root, d))

		for f in files:
			fullpath = os.path.join(root, f)
			# i dont think this is necessary
			# sha1 = hashlib.sha1()
			# sha1.update((f + str(os.path.getsize(fullpath))).encode('utf-8'))
			# sha1.hexdigest()
			if f.upper() in FILES_EXCEPTIONS:
				continue

			key = str(os.path.getsize(fullpath)) + f
			files_orig[key] = {'root': root, 'file': f}

	# equal = []
	# move the same files to the same source path
	for root, dirs, files in os.walk(dest):
		for f in files:
			fullpath = os.path.join(root, f)
			key = (str(os.path.getsize(fullpath)) + f)

			# found equal files
			if key in files_orig:
				rel_path = os.path.relpath(files_orig[key]['root'], orig)
				rel_path = rel_path if rel_path != '.' else dest

				# create missing dirs in the destination
				to_create = os.path.join(dest, rel_path)
				if not os.path.exists(to_create):
					# Python 3.2+
					os.makedirs(to_create, exist_ok=True)

					# Python 2.7+
					# try:
					#     os.makedirs(to_create)
					# except OSError:
					#     if not os.path.isdir(to_create):
					#         raise

				to = os.path.join(dest, rel_path, f)
				# different paths, so move instead of copy
				if to != fullpath:
					subpath_from = onlysubpath(initialroot=dest, currentroot=fullpath)
					subpath_to   = onlysubpath(initialroot=dest, currentroot=to)
					try:
						shutil.move(fullpath, to)
						# log('DEBUG: move_equals - FROM: '+fullpath + ' TO: '+to)
						log('\t\tMOVED - FROM: ' + subpath_from + ' TO: ' + subpath_to)
						count_moved += 1
						# equal.append('FROM: ' + fullpath + ' - TO: '+ to)
					except Exception as e:
						# log('\t\tERROR MOVE - FROM: ' + subpath_from + ' TO: ' + subpath_to)
						log('\t\tERROR MOVE_EQUALS (SHUTIL.MOVE): ' + str(e))
					
					set_original_attrs(os.path.join(files_orig[key]['root'], files_orig[key]['file']), to)

	# try to maintain the same file attributes in destination
	for d in all_orig_dirs:
		path_in_dest = getNewPath(dest, '', d, orig)
		if os.path.exists(path_in_dest):
			set_original_attrs(d, path_in_dest)
		
	# print(json.dumps(files_orig, indent=4))
	# print(json.dumps(equal, indent=4))
	return count_moved

def copydir(orig, dest, params = []):
	count_copied = 0
	count_moved = 0
	created_dirs = []
	global FILES_ALWAYS_REPLACE

	if not os.path.exists(orig):
		return count_copied, count_moved

	if try_to_move(params):
		count_moved = move_equals(orig, dest)


	if not os.path.exists(dest):
		os.mkdir(dest)
		#os.chmod(dest, 0o777)
		created_dirs.append({'from': orig, 'to': dest})
	
	# avoid calling the same functions inside the loop
	v_overwrite = None
	v_overwrite = overwrite(params)
	v_isrecursive = None
	v_isrecursive = isrecursive(params)

	#shutil.copytree(orig, dest)
	for root, dirs, files in os.walk(orig):
		overwrite_current = False

		if not v_isrecursive:
			# remove directories
			while len(dirs) > 0:
				dirs.pop()
	
		for d in dirs:
			newdir = getNewPath(dest, d, root, orig)
			if not os.path.exists(newdir):
				os.mkdir(newdir)
				created_dirs.append({'from': os.path.join(root, d), 'to': newdir})
				
		for f in files:
			originalpath = os.path.join(root, f)
			newfilepath = getNewPath(dest, f, root, orig)
			overwrite_current = False

			# same name but different sizes, therefore overwrites(only this file)
			if os.path.exists(newfilepath) and (os.path.getsize(newfilepath) != os.path.getsize(originalpath)):
				overwrite_current = True

			if f.upper() in FILES_ALWAYS_REPLACE:
				overwrite_current = True

			if not os.path.exists(newfilepath) or v_overwrite or overwrite_current:
				if not check_disk_space(originalpath, newfilepath):
					return count_copied, count_moved

				try:
					fsrc = open(originalpath, 'rb')
				except IOError:
					msg = 'ERROR COPYDIR: COULD NOT OPEN FILE: ' + originalpath
					on_error_log(msg, msg)
					return count_copied, count_moved
				try:
					fdst = open(newfilepath, 'wb')
				except IOError:
					msg = 'ERROR COPYDIR: COULD NOT OPEN FILE: ' + newfilepath
					on_error_log(msg, msg)
					return count_copied, count_moved

				modified_copyfileobj(fsrc, fdst)
				fsrc.close()
				fdst.close()
				# Windows does not release the files!!! Having problems with win32file.CreateFile afterwards
				fsrc = None
				fdest= None
				
				count_copied += 1
				subpath = onlysubpath(initialroot=orig, currentroot=root)
				log('\t\tCOPIED: ' + subpath + '\\' + f)
				set_original_attrs(originalpath, newfilepath)

				# i was having some problems on CreateFile in the following: pywintypes.error: (32, 'CreateFile', 'The process cannot access the file because it is being used by another process.')
				# so i changd, to close() explicity
				'''
				with open(originalpath, 'rb') as fsrc:
					with open(newfilepath, 'wb') as fdst:
						#shutil.copyfileobj(fsrc, fdst)
						modified_copyfileobj(fsrc, fdst)
				shutil.copystat(originalpath, newfilepath)
				'''

	# try to maintain the same file attributes in destination
	for c_dir in created_dirs:
		set_original_attrs(c_dir['from'], c_dir['to'])

	return count_copied, count_moved

def removediff(toremovepath, comparepath, params = []):
	total_removed = 0

	# avoid calling the same function inside the loop
	v_isrecursive = None
	v_isrecursive = isrecursive(params)

	for root, dirs, files in os.walk(toremovepath):
		if not v_isrecursive:
			#remove directories
			while len(dirs) > 0:
				dirs.pop()

		for d in dirs:
			dircompare = getNewPath(comparepath, d, root, toremovepath)
			if not os.path.exists(dircompare):
				removedir = os.path.join(root, d)
				
				#total_removed += sum([len(files) for root, dirs, files in os.walk(removedir)])
				#count number of files inside a directory and LOG removed ones
				for r, d, files_r in os.walk(removedir):
					total_removed += len(files_r)
					for f in files_r:
						#log using only the different part of the path
						log('\t\tREMOVED: ' + r.replace(root, '') + '\\' + f)
				
				try:
					# usually this will avoid an exception
					os.chmod(removedir, stat.S_IWRITE)

					shutil.rmtree(removedir)
				except:
					msg = 'ERROR REMOVEDIFF: SHUTIL.RMTREE - FILE: ' + removedir
					on_error_log(msg, msg)
					return total_removed
		
		for f in files:
			filecompare = getNewPath(comparepath, f, root, toremovepath)
			if not os.path.exists(filecompare):
				pathremove = os.path.join(root, f)
				os.chmod(pathremove, stat.S_IWRITE)
				os.remove(pathremove)
				
				subpath = onlysubpath(initialroot=toremovepath, currentroot=root)
				log('\t\tREMOVED: ' + subpath + '\\' + f)
				total_removed += 1
	
	return total_removed

#TODO: use named tuples?
def syncdir(original, tosync, params = []):
	if not os.path.exists(original):
		return 0, 0, 0

	# try to move files before, if possible
	# if there is duplicate files in the original path inside different folders, this function will move the files and then copy the same files
	total_moved = 0
	if try_to_move(params):
		total_moved = move_equals(original, tosync)
		# we don't need try to move the files once again
		del params['try_to_move']

	if not os.path.exists(tosync):
		total_removed = 0
	else:	
		total_removed = removediff(tosync, original, params)
	
	global ERROR_MSG
	if ERROR_MSG != '':
		return total_removed, 0, total_moved

	total_copied, c_total_moved  = copydir(original, tosync, params)
	return total_removed, total_copied, total_moved
		
def log(text):
	global LOG

	data = '[' + datetime.datetime.now().strftime('%d/%m/%Y') + ' ' + datetime.datetime.now().time().strftime('%H:%M:%S') + ']'
	LOG.write(data + ' ' + text + '\n')

def log_endblock():
	log(''.join(['-' for x in range(1,140)]))

def header_logs(operation, type='sync'):
	global DEVICELABELS

	log('\tSTART ' + type.upper() + ' - ' + operation['orig'] + ' TO ' + operation['dest'])
	# conditions in vars, better to readability
	cond1 = operation['orig_serial'] in DEVICELABELS
	cond2 = operation['dest_serial'] in DEVICELABELS
	if cond1 and cond2:
		log('\t' + DEVICELABELS[operation['orig_serial']] + ' -> ' + DEVICELABELS[operation['dest_serial']])
	else:
		log('\tNO DEVICE LABEL EXPECIFIED')

	print('Starting ' + type + ' --> ' + operation['orig'] + ' to ' + operation['dest'])
	sys.stdout.flush()

def on_error_log(log_text, error_text):
	global ERROR_MSG
	log(log_text)
	log_endblock()
	ERROR_MSG = error_text

def get_serial_drive_map():
	serial_drive_map = {}

	# [:-1] remove the last null byte
	drives = win32api.GetLogicalDriveStrings()[:-1].split('\x00')
	for d in drives:
		try:
			name, serial_number, max_len_filename, flags, filesystem_name = win32api.GetVolumeInformation(d)
			# aways get the positive number (2 complement). See: https://www.cs.cornell.edu/~tomf/notes/cps104/twoscomp.html
			serial_number = serial_number & 0xffffffff if serial_number < 0 else serial_number
			# d[:-1] remove the backslash
			serial_drive_map[serial_number] = d[:-1]
		except:
			#ignoring 'The device is not ready.' errors. (CD/ROM drives, etc)
			#log maybe?
			pass

	return serial_drive_map	

def format_time_toprint(seconds):
	hor = 0
	min = 0
	sec = seconds
	if sec > 59:
		min = sec // 60
		sec = sec % 60

		if min > 59:
			hor = min // 60
			min = min % 60

	time_str = str(hor)+'h ' + str(min)+'m ' + str(sec)+'s'

	return time_str	

def get_operations():
	global OPERATIONS
	serial_drive_map = get_serial_drive_map()
	#print (json.dumps(serial_drive_map, indent=4))

	result = []
	# remove ones that have not the correspondent drives plugged
	# add the drive prefix on paths
	for o in OPERATIONS:
		if o['orig_serial'] in serial_drive_map and o['dest_serial'] in serial_drive_map:
			o['orig'] = serial_drive_map[o['orig_serial']] + o['orig']
			o['dest'] = serial_drive_map[o['dest_serial']] + o['dest']
			result.append(o)

	return result

def main():
	operations = get_operations()	
	#print(json.dumps(operations, indent=4))
	#return 0

	start = time.clock()
	total_operations = len(operations)
	total_moved = 0
	total_removed = 0
	total_copied = 0
	global ERROR_MSG

	log('START BACKUP')

	print ('Starting operations --> ' + str(total_operations) + ' pending')
	print()
	sys.stdout.flush()

	for a in operations:
		params = []
		if 'params' in a:
			params = a['params']

		if a['type'] == 'copy':
			header_logs(a, 'copy')

			start_loop = time.clock()
			c, m = copydir(a['orig'], a['dest'], params)
			if ERROR_MSG != '':
				print ('Error: ' + ERROR_MSG)
				return 0

			total_copied += c
			total_moved += m
			end_loop = time.clock()

			time_str = format_time_toprint(int(round(end_loop - start_loop)))
			print ('Copy ended    --> Time elapsed: ' + time_str)
			sys.stdout.flush()

			log('\t\tFILES MOVED: ' + str(m))
			log('\t\tFILES COPIED: ' + str(c))
			log('\t\tTIME USED: ' + time_str)
			log('\tEND COPY - ' + a['orig'] + ' TO ' + a['dest'])

		elif a['type'] == 'sync':
			header_logs(a, 'sync')

			start_loop = time.clock()
			r, c, m = syncdir(a['orig'], a['dest'], params)
			if ERROR_MSG != '':
				print ('Error: ' + ERROR_MSG)
				return 0

			total_moved += m
			total_removed += r
			total_copied += c
			end_loop = time.clock()

			time_str = format_time_toprint(int(round(end_loop - start_loop)))
			print ('Sync ended    --> time elapsed: ' + time_str)
			sys.stdout.flush()

			log('\t\tFILES MOVED: ' + str(m))
			log('\t\tFILES REMOVED: ' + str(r))
			log('\t\tFILES COPIED: ' + str(c))
			log('\t\tTIME USED: ' + time_str)
			log('\tEND SYNC - ' + a['orig'] + ' TO ' + a['dest'])

		else:
			print('Unknown operation')
			sys.stdout.flush()

		total_operations -= 1
		print('Finished      --> ' + str(total_operations) + ' pending')
		print()
		sys.stdout.flush()
			
	end = time.clock()

	total_str = format_time_toprint(int(round(end - start)))
	print('Total time: ' + total_str)
	sys.stdout.flush()

	log('\tTOTAL FILES MOVED: ' + str(total_moved))
	log('\tTOTAL FILES REMOVED: ' + str(total_removed))
	log('\tTOTAL FILES COPIED: ' + str(total_copied))
	log('\tTOTAL TIME USED: ' + total_str)
	log('END BACKUP')
	log_endblock()

if __name__ == '__main__':
	main()
	LOG.close()