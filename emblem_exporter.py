#!/usr/bin/env python3
'''
@author: Winter Snowfall
@version: 1.12
@date: 23/06/2023

Warning: Built for use with python 3.6+
'''

import json
import logging
import argparse
import subprocess
import signal
import os

# logging configuration block
LOGGER_FORMAT = '%(asctime)s %(levelname)s >>> %(message)s'
# logging level for other modules
logging.basicConfig(format=LOGGER_FORMAT, level=logging.ERROR)
logger = logging.getLogger(__name__)
# logging level for current logger
logger.setLevel(logging.INFO) # DEBUG, INFO, WARNING, ERROR, CRITICAL

# CONSTANTS
EXPECTED_METADATA_FIELDS = 5
PATH_METADATA_FIELD_INDEX = 1
EMBLEM_METADATA_FIELD_INDEX = 4
MIN_PROGRESS_INDICATOR_ITEMS = 10000
PROGRESS_INDICATOR_PERCENT_INTERVAL = 10
TYPE_FILTERS = ('file', 'folder')

def sigterm_handler(signum, frame):
    logger.debug('Stopping script due to SIGTERM.')
    
    raise SystemExit(0)

def sigint_handler(signum, frame):
    logger.debug('Stopping script due to SIGINT.')
    
    raise SystemExit(0)

def path_crawler(base_path, type_filter, recurse):
    items_to_process = []
    
    for dirpath, dirnames, filenames in os.walk(base_path):
        logger.debug(f'PC >>> Processing: {dirpath}')
        
        if not type_filter or type_filter == TYPE_FILTERS[0]:
            for file in filenames:
                items_to_process.append(os.path.join(dirpath, file))
        if not type_filter or type_filter == TYPE_FILTERS[1]:
            for dirname in dirnames:
                items_to_process.append(os.path.join(dirpath, dirname))
        
        if not recurse:
            break
    
    return items_to_process

def scan_emblems(scan_path, json_file, type_filter, recurse, setonly, purge, clear):
    json_data = {}
    
    logger.debug(f'Scan path: {scan_path}')
    
    if recurse:
        logger.warning('Recursive scans can take a VERY long time.')
    
    items_to_process = path_crawler(scan_path, type_filter, recurse)
    nr_items_to_process = len(items_to_process)
    
    logger.info(f'Number of items to scan for emblems: {nr_items_to_process}')
    
    if nr_items_to_process > MIN_PROGRESS_INDICATOR_ITEMS:
        show_progress = True
    else:
        show_progress = False
    
    processed_items = 0
    last_processed_percentage = 0
    processed_percentage = 0
    emblems_found = 0
    emblems_exported = 0
    emblems_cleared = 0
    emblems_purged = 0
    
    logger.info('Starting emblems scan...')
    
    try:
        for item in items_to_process:
            if show_progress:
                processed_items += 1
            
            try:
                emblem_export_output = subprocess.run(['gio', 'info', '-a', 'metadata::emblems', item], 
                                                      stdout=subprocess.PIPE, text=True, check=True)
                emblem_metadata = emblem_export_output.stdout.splitlines()
                
                if (len(emblem_metadata) == EXPECTED_METADATA_FIELDS and 
                    'metadata::emblems' in emblem_metadata[EMBLEM_METADATA_FIELD_INDEX]):
                    try:
                        path = emblem_metadata[PATH_METADATA_FIELD_INDEX].split(': ')[1]
                        emblems = emblem_metadata[EMBLEM_METADATA_FIELD_INDEX].split(': ')[1][1:-1].split(', ')
                        
                        # items with unset emblems will keep the attribute, but with a string, 
                        # not vstring, value of '[]' (this is either indended or an oversight) - 
                        # in this case, simply save an empty list in the JSON export file, 
                        # since it will enable clearing any existing emblem values on import
                        if len(emblems) == 1 and emblems[0] == '':
                            emblems = []
                        
                        if not clear:
                            if setonly and len(emblems) == 0:
                                logger.info(f'Ignoring empty emblem for: {path}')
                            else:
                                logger.info(f'Found {emblems} emblem(s) for: {path}')
                                json_data.update({path: emblems})
                                emblems_exported += 1
                        
                        else:
                            try:
                                # in order to purge emblems from an item and mark it as if
                                # it never had emblems attached, one must remove the attribute
                                # entirely - this is done by using the 'unset' value type
                                if purge:
                                    emblems_found += 1
                                    
                                    subprocess.run(['gio', 'set', '-t', 'unset', path, 
                                                    'metadata::emblems'], check=True)
                                    emblems_purged += 1
                                    
                                    logger.info(f'Found and purged emblems for: {path}')
                                    
                                # a string, not vstring, value of '[]' is set by Caja/Nautilus
                                # on items that have previously had emblem(s) but all entries
                                # have since been removed - replicate this behavior
                                else:
                                    if len(emblems) > 0:
                                        emblems_found += 1
                                        
                                        subprocess.run(['gio', 'set', path, 
                                                        'metadata::emblems', '[]'], check=True)
                                        emblems_cleared += 1
                                
                                        logger.info(f'Found and cleared emblems for: {path}')
                                    else:
                                        logger.debug(f'Found empty emblem for: {path}')
                                
                            except:
                                raise
                    
                    except:
                        raise
                
            except SystemExit:
                raise
            
            except:
                logger.warning(f'Failed to process: {item}')
            
            if show_progress:
                processed_percentage = processed_items * 100 // nr_items_to_process
                
                # update scan progress in 5% increments
                if (processed_percentage % PROGRESS_INDICATOR_PERCENT_INTERVAL == 0 and 
                    last_processed_percentage != processed_percentage):
                    last_processed_percentage = processed_percentage
                    # no point in showing 100%, as 0% is also rightfully ignored
                    if processed_percentage != 100:
                        logger.info(f'Proccessed {processed_items} items, {processed_percentage}% of total.')
    
    # allow the export of partially completed scans
    except SystemExit:
        logger.warning('Halting emblems scan due to termination signal!')
    
    logger.info('Emblems scan completed.')
    
    if clear:
        if emblems_found > 0:
            if purge:
                logger.info(f'Succesfully purged {emblems_purged}/{emblems_found} emblems.')
            else:
                logger.info(f'Succesfully cleared {emblems_cleared}/{emblems_found} emblems.')
    
    else:
        if len(json_data) > 0:
            json_export = json.dumps(json_data, sort_keys=True, indent=4, 
                                     separators=(',', ': '), ensure_ascii=False)
            
            logger.debug(f'JSON: {json_export}')
            
            with open(json_file, 'w') as file:
                file.write(json_export)
            
            logger.info('JSON export completed.')
            
            logger.info(f'Succesfully exported {emblems_exported} emblems.')
        
        else:
            logger.warning('Nothing to export!')

def import_emblems(json_file):
    logger.info('Starting emblems import...')
    
    with open(json_file, 'r') as file:
        file_content = file.read()
    
    try:
        json_data = json.loads(file_content)
        items_to_process = len(json_data)
    
    except json.JSONDecodeError:
        logger.critical('Invalid JSON file structure!')
        raise SystemExit(5)
    
    if items_to_process > 0:
        logger.info(f'Number of emblems to apply: {items_to_process}')
        
        processed_items = 0
        
        for key in json_data:
            if os.path.isfile(key) or os.path.isdir(key):
                emblems = json_data[key]
                
                logger.info(f'Applying {emblems} emblem(s) to: {key}')
                
                try:
                    if len(emblems) == 0:
                        # a string, not vstring, value of '[]' is set by Caja/Nautilus 
                        # on items that have previously had emblem(s) but all entries 
                        # have since been removed - replicate this behavior
                        subprocess.run(['gio', 'set', key, 
                                        'metadata::emblems', '[]'], check=True)
                    else:
                        subprocess.run(['gio', 'set', '-t', 'stringv', key, 
                                        'metadata::emblems', *emblems], check=True)
                    
                    processed_items += 1
                
                except:
                    logger.warning(f'Failed to import: {key}')
            
            else:
                logger.warning(f'Path not found: {key}')
        
        logger.info('Emblems import completed.')
        
        logger.info(f'Succesfully applied {processed_items}/{items_to_process} emblems.')
    
    else:
        logger.warning('Nothing to import!')

if __name__ == '__main__':
    # catch SIGTERM and exit gracefully
    signal.signal(signal.SIGTERM, sigterm_handler)
    # catch SIGINT and exit gracefully
    signal.signal(signal.SIGINT, sigint_handler)
    
    parser = argparse.ArgumentParser(description=('GIO wrapper for Caja/Nautilus emblems import/export and clearing'), 
                                     add_help=False)
    
    parser.add_argument('source')
    parser.add_argument('destination', nargs='?', default=None)
    
    group = parser.add_mutually_exclusive_group(required=True)
    optional = parser.add_argument_group('optional arguments')
    
    group.add_argument('-i', '--import', help='Import emblem data from a JSON file', action='store_true')
    group.add_argument('-e', '--export', help='Export emblem data from a specified path to a JSON file', 
                       action='store_true')
    group.add_argument('-c', '--clear', help='Clear emblem data in a specified path', action='store_true')
    
    optional.add_argument('-h', '--help', action='help', help='show this help message and exit')
    optional.add_argument('-r', '--recursive', help='Recursively scan the path for emblems', 
                          action='store_true')
    optional.add_argument('-s', '--setonly', help='Ignore previously unset/cleared emblems during exports', 
                          action='store_true')
    # removing the meta-attribute (or purging) is also useful for testing or restoring a path 
    # to its original "pristine" state, before any emblem data was ever applied with Caja/Nautilus
    optional.add_argument('-p', '--purge', help='Remove emblem data along with its meta-attribute', 
                          action='store_true')
    optional.add_argument('-t', '--type', help='Type filter that can be set to either "file" or "folder"', 
                          default=None)
    
    args = parser.parse_args()
    
    # ignore unsupported values by clearing the filter
    if args.type and args.type not in TYPE_FILTERS:
        logger.warning(f'Ignoring unsupported type filter value of "{args.type}".')
        args.type = None
    
    if args.export:
        if os.path.isdir(args.source):
            if os.path.isdir(os.path.dirname(os.path.abspath(args.destination))):
                scan_emblems(args.source, args.destination, args.type,  
                             args.recursive, args.setonly, None, False)
            else:
                logger.critical('Invalid export path!')
                raise SystemExit(2)
        else:
            logger.critical('Invalid source directory!')
            raise SystemExit(1)
    
    elif args.clear:
        if os.path.isdir(args.source):
            if args.purge:
                option = input('ALL EMBLEM DATA IN THE SPECIFIED PATH WILL BE PURGED! PROCEED (Y/N)? ')
            else:
                option = input('ALL EMBLEM DATA IN THE SPECIFIED PATH WILL BE LOST! PROCEED (Y/N)? ')
            
            if option.upper() == 'Y':
                scan_emblems(args.source, None, args.type, args.recursive, 
                             None, args.purge, True)
            else:
                logger.info('Emblem clearing aborted.')
        else:
            logger.critical('Invalid clearing directory!')
            raise SystemExit(3)
    
    else:
        if os.path.isfile(args.source):
            import_emblems(args.source)
        else:
            logger.critical('Invalid source JSON file!')
            raise SystemExit(4)
